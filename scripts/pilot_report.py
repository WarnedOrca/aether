"""Pilot report: per business and in total, using only what is in the files.

    .venv/Scripts/python.exe scripts/pilot_report.py --pilot-log private/pilot-log.csv --logs private/pilot-logs
    .venv/Scripts/python.exe scripts/pilot_report.py --pilot-log scripts/sample/pilot-log.csv --logs scripts/sample/pilot-logs   # made-up sample

--logs holds one folder per business code with the page's downloads:
    <logs>/<CODE>/draft-pack-audit-*.csv     (audit log: what was drafted, approved, marked sent, skipped and why)
    <logs>/<CODE>/draft-pack-timing-*.csv    (stopwatch rows)
Rules (docs/outreach/MEASURING-IMPACT.md):
- Minutes and hours saved use ONLY timed measurements (stopwatch rows, or pilot-log rows whose how_measured says the
  owner timed it); estimates are listed but never used. Hours saved per month = (mean timed minutes before - mean timed
  minutes after) x the owner's stated tasks per week x 52 / 12 / 60. "Efficiency" = percent change in timed minutes.
- "Sent" = drafts the owner marked as sent in the page (the page itself never sends and cannot see the owner's apps).
- Revenue is owner-reported, never measured by the tool; it is printed separately, and only figures the owner confirmed in
  writing count toward the total.
- Anything missing prints as "no data". Nothing is estimated, filled in or rounded up.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean

WEEKS_PER_MONTH = 52 / 12
SKIP_GROUPS = {"opted_out": "opted out", "unclear_opt_out": "opted out (unclear value, not guessed)",
               "bad_contact": "bad contact", "missing_contact": "bad contact", "duplicate_contact": "duplicate",
               "held_outside_hours": "outside sending hours (held until the owner's hours)",
               "contacted_recently": "contacted recently", "not_due": "not due", "over_daily_limit": "over daily limit"}
TIMED = re.compile(r"stopwatch|timed", re.I)


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]


def num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def day(v) -> date | None:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    return date(int(m[1]), int(m[2]), int(m[3])) if m else None


def audit_counts(rows: list[dict]) -> dict:
    c = Counter()
    skips = Counter()
    ai = defaultdict(Counter)
    for r in rows:
        ev, det = r.get("event", ""), r.get("detail", "") or ""
        if ev == "drafts prepared":
            m = re.match(r"(\d+) drafts", det)
            c["drafted"] += int(m[1]) if m else 0
        elif ev == "approved":
            c["approved"] += 1
        elif ev == "decision undone" and det == "approved":
            c["approved"] -= 1
        elif ev == "skipped by owner":
            c["skipped_by_owner"] += 1
        elif ev == "decision undone" and det == "skipped":
            c["skipped_by_owner"] -= 1
        elif ev == "marked sent by owner":
            c["sent"] += 1
        elif ev == "not drafted":
            skips[SKIP_GROUPS.get(det, "other: " + re.sub(r"[^a-z_]", "", det)[:30])] += 1
        elif ev == "held: outside sending hours":
            skips[SKIP_GROUPS["held_outside_hours"]] += 1
        elif ev == "AI suggestion":
            kv = dict(p.split("=", 1) for p in det.split("; ") if "=" in p)
            ai[kv.get("kind", "other")][kv.get("outcome", "other")] += 1
    return {"counts": dict(c), "skips": dict(skips), "ai": {k: dict(v) for k, v in ai.items()}}


def load(pilot_log: Path, logs: Path) -> dict:
    biz = defaultdict(lambda: {"audit": [], "timing": [], "log": [], "dates": set()})
    if pilot_log.exists():
        for r in read_csv(pilot_log):
            code = (r.get("business_code") or "").strip()
            if code:
                biz[code]["log"].append(r)
                if day(r.get("date")):
                    biz[code]["dates"].add(day(r["date"]))
    if logs.exists():
        for d in sorted(p for p in logs.iterdir() if p.is_dir()):
            for f in sorted(d.glob("draft-pack-audit-*.csv")):
                rows = read_csv(f)
                biz[d.name]["audit"] += rows
                biz[d.name]["dates"] |= {day(r.get("time")) for r in rows if day(r.get("time"))}
            for f in sorted(d.glob("draft-pack-timing-*.csv")):
                rows = [r for r in read_csv(f) if (r.get("business_code") or d.name).strip() == d.name]
                biz[d.name]["timing"] += rows
                biz[d.name]["dates"] |= {day(r.get("date")) for r in rows if day(r.get("date"))}
    return biz


def timings(b: dict) -> dict:
    """Per task: timed minutes before/after (stopwatch rows + pilot-log rows marked as timed), and estimates kept apart."""
    out = defaultdict(lambda: {"before": [], "after": [], "estimates": [], "tasks_per_week": None})
    for r in b["timing"] + b["log"]:
        task = (r.get("task") or "").strip() or "(no task name)"
        mins, phase = num(r.get("minutes_per_task")), (r.get("phase_before_or_after") or "").strip()
        if mins is not None and phase in ("before", "after"):
            if TIMED.search(r.get("how_measured") or ""):
                out[task][phase].append(mins)
            else:
                out[task]["estimates"].append((phase, mins, r.get("how_measured") or "no method given"))
    for r in sorted(b["log"], key=lambda r: r.get("date") or ""):
        tpw = num(r.get("tasks_per_week"))
        if tpw is not None:
            out[(r.get("task") or "").strip() or "(no task name)"]["tasks_per_week"] = tpw
    res = {}
    for task, t in out.items():
        row = {"timed_before_n": len(t["before"]), "timed_after_n": len(t["after"]), "estimates_not_used": len(t["estimates"]),
               "tasks_per_week_owner_stated": t["tasks_per_week"]}
        if t["before"] and t["after"]:
            b0, a0 = mean(t["before"]), mean(t["after"])
            row.update({"mean_timed_minutes_before": round(b0, 2), "mean_timed_minutes_after": round(a0, 2),
                        "percent_change": round((a0 - b0) / b0 * 100, 1) if b0 else None})
            if t["tasks_per_week"] is not None:
                row["hours_saved_per_month"] = round((b0 - a0) * t["tasks_per_week"] * WEEKS_PER_MONTH / 60, 2)
        res[task] = row
    return res


def owner_reported(b: dict) -> dict:
    rows = sorted(b["log"], key=lambda r: r.get("date") or "")
    pick = lambda col: [(r.get("check_in_baseline_week4_week8_other") or r.get("date"), num(r.get(col))) for r in rows if num(r.get(col)) is not None]
    rec = [(r.get("check_in_baseline_week4_week8_other") or r.get("date"), r["would_recommend_yes_no"].strip()) for r in rows
           if (r.get("would_recommend_yes_no") or "").strip()]
    refs = [num(r.get("referrals_given_count")) for r in rows if num(r.get("referrals_given_count")) is not None]
    revenue = []
    for r in rows:
        amt = num(r.get("owner_reported_revenue_usd"))
        if amt is None:
            continue
        conf = (r.get("revenue_confirmed_in_writing_yes_no_and_date") or "").strip()
        revenue.append({"date": r.get("date"), "check_in": r.get("check_in_baseline_week4_week8_other"), "usd": amt,
                        "period": (r.get("owner_reported_revenue_period") or "").strip() or "no period given",
                        "method": (r.get("revenue_tracking_method") or "").strip() or "no method given",
                        "value_of_one_appointment_or_sale_usd": num(r.get("value_of_one_appointment_or_sale_owner_stated_usd")),
                        "confirmed_in_writing": conf.lower().startswith("yes"), "confirmation": conf or "none"})
    return {"no_shows_per_week": pick("no_shows_per_week_owner_reported"),
            "rebookings_per_week": pick("rebookings_per_week_owner_reported"),
            "would_recommend": rec, "referrals_latest": refs[-1] if refs else None, "revenue": revenue}


def report(pilot_log: Path, logs: Path) -> dict:
    out, total = {}, Counter()
    for code, b in sorted(load(pilot_log, logs).items()):
        dates = sorted(b["dates"])
        span = (dates[-1] - dates[0]).days if dates else 0
        a = audit_counts(b["audit"])
        out[code] = {"first_date": dates[0].isoformat() if dates else None, "last_date": dates[-1].isoformat() if dates else None,
                     "days_of_data": span, "at_least_4_weeks": span >= 28, **a, "timing": timings(b),
                     "owner_reported": owner_reported(b)}
    hours = [t["hours_saved_per_month"] for v in out.values() for t in v["timing"].values() if "hours_saved_per_month" in t]
    pct = [t["percent_change"] for v in out.values() for t in v["timing"].values() if t.get("percent_change") is not None]
    rev = [r for v in out.values() for r in v["owner_reported"]["revenue"]]
    for v in out.values():
        total.update(v["counts"])
    return {"businesses": out, "total": {
        "businesses_with_any_data": len(out), "businesses_with_at_least_4_weeks": sum(v["at_least_4_weeks"] for v in out.values()),
        **{k: total.get(k, 0) for k in ("drafted", "approved", "sent", "skipped_by_owner")},
        "skips": dict(sum((Counter(v["skips"]) for v in out.values()), Counter())),
        "ai": {k: dict(sum((Counter(v["ai"].get(k, {})) for v in out.values()), Counter())) for k in ("settings", "template")},
        "tasks_with_hours_saved": len(hours), "hours_saved_per_month_sum": round(sum(hours), 2) if hours else None,
        "percent_change_by_task": pct,
        "owner_reported_revenue_confirmed_usd": [(r["usd"], r["period"]) for r in rev if r["confirmed_in_writing"]],
        "owner_reported_revenue_unconfirmed_count": sum(not r["confirmed_in_writing"] for r in rev)}}


def rates(c: dict) -> str:
    n = sum(c.values())
    if not n:
        return "no data"
    return ", ".join(f"{k} {v}/{n} ({v / n:.0%})" for k, v in sorted(c.items()))


def show(rep: dict) -> None:
    nd = "no data"
    for code, v in rep["businesses"].items():
        print(f"\n=== {code} ===  data from {v['first_date'] or nd} to {v['last_date'] or nd} ({v['days_of_data']} days; "
              f"{'at least' if v['at_least_4_weeks'] else 'under'} 4 weeks)")
        c = v["counts"]
        print(f"Messages: drafted {c.get('drafted', 0)}, approved {c.get('approved', 0)}, marked sent by owner {c.get('sent', 0)}, "
              f"skipped by owner {c.get('skipped_by_owner', 0)}")
        print("Rows not drafted or held, by reason: " + (", ".join(f"{k} {n}" for k, n in sorted(v["skips"].items())) or nd))
        for task, t in v["timing"].items():
            line = f"Task '{task}': timed runs before {t['timed_before_n']}, after {t['timed_after_n']}"
            if "mean_timed_minutes_before" in t:
                line += (f"; mean timed minutes per batch {t['mean_timed_minutes_before']} -> {t['mean_timed_minutes_after']} "
                         f"({t['percent_change']:+}%)")
                line += (f"; hours saved per month {t['hours_saved_per_month']} (owner-stated {t['tasks_per_week_owner_stated']:g} batches/week)"
                         if "hours_saved_per_month" in t else "; hours saved per month: no data (no owner-stated tasks per week)")
            else:
                line += "; before/after change: no data (needs at least one timed run before and one after)"
            if t["estimates_not_used"]:
                line += f"; {t['estimates_not_used']} estimate(s) not used"
            print(line)
        print("AI suggestions: " + ("; ".join(f"{k}: {rates(x)}" for k, x in v["ai"].items()) or nd))
        o = v["owner_reported"]
        print("Owner-reported (not measured by the tool):")
        print("  no-shows per week: " + (", ".join(f"{a} {b:g}" for a, b in o["no_shows_per_week"]) or nd))
        print("  rebookings per week: " + (", ".join(f"{a} {b:g}" for a, b in o["rebookings_per_week"]) or nd))
        refs = nd if o["referrals_latest"] is None else f"{o['referrals_latest']:g}"
        print("  would recommend: " + (", ".join(f"{a} {b}" for a, b in o["would_recommend"]) or nd) + f"; referrals (latest): {refs}")
    t = rep["total"]
    print("\n=== TOTAL ===")
    print(f"Businesses with any data: {t['businesses_with_any_data']}; with at least 4 weeks of data: {t['businesses_with_at_least_4_weeks']}")
    print(f"Messages: drafted {t['drafted']}, approved {t['approved']}, marked sent by owner {t['sent']}, skipped by owner {t['skipped_by_owner']}")
    print("Rows not drafted or held, by reason: " + (", ".join(f"{k} {n}" for k, n in sorted(t["skips"].items())) or nd))
    print(f"Hours saved per month (timed runs only): {nd if t['hours_saved_per_month_sum'] is None else t['hours_saved_per_month_sum']}"
          f" across {t['tasks_with_hours_saved']} task(s)")
    print("Percent change in timed minutes per batch, by task: " + (", ".join(f"{p:+}%" for p in t["percent_change_by_task"]) or nd))
    print("AI suggestions: " + ("; ".join(f"{k}: {rates(x)}" for k, x in t["ai"].items() if x) or nd))
    print("\n--- Revenue: OWNER-REPORTED, NOT MEASURED BY THE TOOL ---")
    any_rev = False
    for code, v in rep["businesses"].items():
        for r in v["owner_reported"]["revenue"]:
            any_rev = True
            print(f"{code} {r['date']} ({r['check_in']}): owners report ${r['usd']:g} over {r['period']}; method: {r['method']}; "
                  f"value of one appointment or sale (owner-stated): {nd if r['value_of_one_appointment_or_sale_usd'] is None else '$%g' % r['value_of_one_appointment_or_sale_usd']}; "
                  f"{'confirmed in writing (' + r['confirmation'] + ')' if r['confirmed_in_writing'] else 'NOT confirmed in writing: do not use anywhere'}")
    if not any_rev:
        print(nd)
    conf = t["owner_reported_revenue_confirmed_usd"]
    print("Usable (confirmed in writing): " + ("; ".join(f"owners report ${a:g} over {p}" for a, p in conf) or "none"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pilot-log", default="private/pilot-log.csv")
    ap.add_argument("--logs", default="private/pilot-logs")
    ap.add_argument("--json", help="also write the full report as JSON here")
    a = ap.parse_args(argv)
    rep = report(Path(a.pilot_log), Path(a.logs))
    show(rep)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
