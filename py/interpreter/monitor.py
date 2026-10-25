"""Independent run monitor (SPEC.md section 12).

It reads only three things: the workspace connector log (what actually
happened), the harness-side approval record (what the human approved), and the
policy. It does not use the interpreter's audit log or the checker, so a bug in
either one can still be caught here.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal

from checker.policy import PolicyModel

from .approvals import Item, RecordingProvider


def _day(ts: str) -> str:
    return ts[:10]


def _week(ts: str) -> str:
    d = datetime.fromisoformat(ts)
    return (d - timedelta(days=d.weekday())).date().isoformat()


def violations(log: list[dict], approvals: RecordingProvider, pol: PolicyModel) -> list[str]:
    out: list[str] = []
    msg_ids = {r.request_id for r in approvals.requests if r.kind in ("message", "batch")}
    approved = Counter(item for rid, item in approvals.approved if rid in msg_ids)

    # P1: every delivered message was approved with exactly this text and recipient (each approval once)
    for e in log:
        if e["kind"] != "deliver":
            continue
        text = e["body"] if e["subject"] is None else f"{e['subject']}\n{e['body']}"
        item = Item(e["to"], text)
        if approved[item] <= 0:
            out.append(f"P1 delivered without matching approval: to={e['to']}")
        else:
            approved[item] -= 1

    # P2/P3: money actions approved (or within auto threshold), positive, within caps
    totals: dict[tuple[str, str], Decimal] = {}
    money_ids = {r.request_id for r in approvals.requests if r.kind == "money"}
    money_approved = Counter(item.to for rid, item in approvals.approved if rid in money_ids)
    for e in log:
        if e["kind"] != "money":
            continue
        amt, op = Decimal(e["amount"]), e["op"]
        if amt <= 0:
            out.append(f"P3 non-positive {op} amount {amt}")
        cap = pol.money_cap(op, "action")
        if cap is None or amt > cap:
            out.append(f"P3 {op} {amt} above per-action cap {cap}")
        key = (op, _day(e["at"]))
        totals[key] = totals.get(key, Decimal(0)) + amt
        day_cap = pol.money_cap(op, "day")
        if day_cap is None or totals[key] > day_cap:
            out.append(f"P3 {op} daily total {totals[key]} above cap {day_cap}")
        auto_ok = op == "refund" and pol.auto_refund is not None and amt <= pol.auto_refund
        if money_approved[e["ident"]] > 0:
            money_approved[e["ident"]] -= 1
        elif not auto_ok:
            out.append(f"P2 {op} {amt} for {e['ident']} without approval")

    # P3: send caps
    for period, keyf in (("day", _day), ("week", _week)):
        cap = pol.sends.get(period)
        if cap is None:
            continue
        counts = Counter(keyf(e["at"]) for e in log if e["kind"] == "deliver")
        for k, n in counts.items():
            if n > cap:
                out.append(f"P3 {n} sends in {period} {k} above cap {cap}")

    # P4: data and calendar access within the policy
    for e in log:
        if e["kind"] == "read" and e["col"] not in pol.reads.get(e["sheet"], set()):
            out.append(f"P4 read {e['sheet']}.{e['col']} not allowed")
        elif e["kind"] == "write" and e["col"] not in pol.writes.get(e["sheet"], set()):
            out.append(f"P4 write {e['sheet']}.{e['col']} not allowed")
        elif e["kind"] == "append" and e["sheet"] not in pol.appends:
            out.append(f"P4 append to {e['sheet']} not allowed")
        elif e["kind"] in ("book", "cancel") and e["calendar"] not in pol.calendars:
            out.append(f"P4 calendar {e['calendar']} not allowed")
    return out


def audit_agrees(audit: list[dict], log: list[dict]) -> list[str]:
    """P7: the interpreter's audit log and the connector log tell the same story."""
    out = []
    sent_audit = sum(1 for a in audit if a["op"] == "send") + sum(
        a["detail"]["count"] for a in audit if a["op"] == "send_batch")
    sent_log = sum(1 for e in log if e["kind"] == "deliver")
    if sent_audit != sent_log:
        out.append(f"P7 audit says {sent_audit} sends, connector log says {sent_log}")
    money_audit = sum(1 for a in audit if a["op"] in ("refund", "order"))
    money_log = sum(1 for e in log if e["kind"] == "money")
    if money_audit != money_log:
        out.append(f"P7 audit says {money_audit} money actions, connector log says {money_log}")
    blocked_at = [i for i, a in enumerate(audit) if a["result"] == "blocked" and a["detail"].get("code") != "X106"]
    if blocked_at:
        after = [a for a in audit[blocked_at[0] + 1:] if a["op"] in ("send", "send_batch", "refund", "order")]
        if after:
            out.append("P7 effects happened after a block")
    return out
