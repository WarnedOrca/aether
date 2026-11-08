"""Deterministic compiler: job spec -> (a) the draft pack page's config, (b) a checked Aether program.

    python -m jobspec.compile '{"template": "follow_up", ...}' [--business "Test Business"]

The same spec always gives the same output. Columns use the canonical names below unless a mapping is given.
"""

from __future__ import annotations

import argparse
import json

from jobspec.spec import TEMPLATES, problems

ROLES = ("name", "phone", "email", "date", "opted_out", "last_contacted")
DEFAULT_COLUMNS = {"name": "name", "phone": "phone", "email": "email", "date": "date", "opted_out": "opted_out",
                   "last_contacted": "last_contacted", "invoice": "invoice", "amount": "amount"}
PROC_NAMES = {"appointment_reminder": "AppointmentReminders", "follow_up": "VisitFollowUps",
              "review_request": "ReviewRequests", "invoice_nudge": "InvoiceReminders"}


class SpecError(ValueError):
    pass


def _check(spec: dict) -> None:
    p = problems(spec)
    if p:
        raise SpecError("; ".join(p))
    if "refuse" in spec:
        raise SpecError(f"refused: {spec['refuse']}")


def tool_config(spec: dict, columns: dict | None = None, business: str = "", review_link: str = "") -> dict:
    """The config object the draft pack page's Core.build() takes (same field names)."""
    _check(spec)
    t = TEMPLATES[spec["template"]]
    cols = {**DEFAULT_COLUMNS, **(columns or {})}
    extra = {k: v for k, v in (("business", business), ("review_link", review_link)) if v}
    return {"map": {r: cols[r] for r in ROLES}, "extra": extra, "text": t["text"], "subject": t["subject"],
            "channel": spec["channel"], "date_mode": t["date_mode"], "date_days": t["date_days"],
            "min_days_since_contact": spec["min_days_since_contact"], "daily_limit": spec["daily_limit"],
            "window": list(spec["send_window"])}


def _aether_text(text: str, row: str, cols: dict, business: str, review_link: str) -> str:
    """Template text -> Aether message text: {name} etc. become row columns with a default, fixed values are inlined."""
    fixed = {"business": business or "us", "review_link": review_link or "our review page"}
    out = text
    for key, value in fixed.items():
        out = out.replace("{" + key + "}", value.replace('"', "'").replace("{", "(").replace("}", ")"))
    for key in ("name", "date", "invoice", "amount"):
        default = " default 'there'" if key == "name" else ""
        out = out.replace("{" + key + "}", "{" + row + "." + cols[key] + default + "}")
    return out


def aether_program(spec: dict, columns: dict | None = None, business: str = "", review_link: str = "") -> str:
    """A checked Aether program equivalent to the spec (policy + procedure)."""
    _check(spec)
    t, name = spec["template"], PROC_NAMES[spec["template"]]
    tpl = TEMPLATES[t]
    cols = {**DEFAULT_COLUMNS, **(columns or {})}
    to_col = cols["phone"] if spec["channel"] == "sms" else cols["email"]
    to_type = "Phone" if spec["channel"] == "sms" else "Email"
    sheet_cols = [(cols["name"], "Text"), (to_col, to_type), (cols["date"], "Date"), (cols["opted_out"], "Text"),
                  (cols["last_contacted"], "Date")]
    if t == "invoice_nudge":
        sheet_cols += [(cols["invoice"], "Text"), (cols["amount"], "Money")]
    read_cols = ", ".join(c for c, _ in sheet_cols)
    start, end = spec["send_window"]
    limit = spec["daily_limit"]
    d, days = tpl["date_mode"], tpl["date_days"]
    when = {"ahead": f"days_between(today(), {cols['date']}) == {days}",
            "ago": f"days_between({cols['date']}, today()) == {days}",
            "overdue": f"days_between({cols['date']}, today()) >= {days}"}[d]
    conds = [when, f"(is_empty({cols['opted_out']}) or {cols['opted_out']} == \"no\")"]
    if spec["min_days_since_contact"] > 0:
        conds.append(f"(is_empty({cols['last_contacted']}) or days_between({cols['last_contacted']}, today()) >= {spec['min_days_since_contact']})")
    body = _aether_text(tpl["text"], "r", cols, business, review_link)
    draft = (f'draft sms to r.{to_col}: "{body}"' if spec["channel"] == "sms"
             else f'draft email to r.{to_col} subject "{tpl["subject"]}": "{body}"')
    return f"""policy OwnerPolicy {{
  allow read Customers({read_cols})
  allow write Customers({cols['last_contacted']})
  allow contact Customers.{to_col}
  limit sends {limit} per day
  send only between {start} and {end}
}}

procedure {name} {{
  about "{tpl['label']} (compiled from a job spec)"
  policy OwnerPolicy
  sheet Customers "Customers" {{ {", ".join(f"{c}: {ty}" for c, ty in sheet_cols)} }}
  trigger every day at {start}

  let all = fetch Customers
  let due = filter all where {" and ".join(conds)}
  for each r in due up to {limit} {{
    let m = {draft}
    let ok = request approval of m from owner timeout 12 hours else skip
    send ok
    update r set {cols['last_contacted']} = today()
  }}
}}
"""


def dry_run(spec: dict, rows: list[dict], business: str = "Test Business") -> dict:
    """Parse, check and run the compiled program on the given made-up rows (canonical column names) under the
    independent monitor, with every approval granted. Returns the delivered messages and any monitor problems."""
    from checker.check import check
    from checker.diagnostics import errors
    from checker.parser import parse_source
    from interpreter.sandbox import DEFAULT_NOW, run_monitored, workspace_for

    src = parse_source(aether_program(spec, business=business))
    (proc,) = src.procedures.values()
    policy = src.policies[proc.policy]
    errs = errors(check(proc, policy))
    if errs:
        raise SpecError(f"checker: {errs[0]}")
    start_h, start_m = (int(x) for x in spec["send_window"][0].split(":"))
    ws = workspace_for(proc, data={"Customers": rows}, now=DEFAULT_NOW.replace(hour=start_h, minute=start_m))
    out = run_monitored(proc, policy, ws)
    sent = [e for e in ws.connector_log if e["kind"] == "deliver"]
    return {"status": out.result.status, "delivered": sent, "monitor_problems": out.problems}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--business", default="")
    args = ap.parse_args()
    spec = json.loads(args.spec)
    print(json.dumps(tool_config(spec, business=args.business), indent=2))
    print(aether_program(spec, business=args.business))


if __name__ == "__main__":
    main()
