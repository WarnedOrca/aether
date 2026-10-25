"""Property-test cases P1-P9 (SPEC.md section 12).

Each function runs one generated case and returns a list of problems; an empty
list means the property held. pytest drives these through Hypothesis, and
eval/run_properties.py drives them over many seeds to log real counts.
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from checker import nodes as N
from checker.check import check
from checker.diagnostics import codes, errors
from checker.mutate import block_defining
from checker.parser import parse_source
from checker.spec_examples import load_examples

from .approvals import ApprovalRequest, Decision, FromFunction
from .sandbox import run_monitored, workspace_for
from .values import EMPTY

EXAMPLES = load_examples()
BEHAVIORS = ["approve", "deny", "timeout", "random", "edit"]

_EDITS = [
    "Hi {ROW.COL}, quick note from us.",       # allowed placeholder (filled in per program)
    "Plain text with no placeholders.",
    "Private: {ROW.PRIVATE}",                   # must be rejected when PRIVATE is deny-reveal
    "Unknown {nobody.thing}",                   # must be rejected
    "Broken {brace",                            # must be rejected
]


def _example(name: str) -> tuple[N.Procedure, N.Policy]:
    p = EXAMPLES.procedures[name]
    return p, EXAMPLES.policies[p.policy]


def provider(behavior: str, rng: random.Random, proc: N.Procedure, policy: N.Policy) -> FromFunction:
    from checker.policy import build_model
    pol = build_model(policy)

    def edit_text(req: ApprovalRequest) -> str:
        # Use a real row variable and column from the program when we can
        row, col, private = "a", "patient", "reason"
        for s in _walk(proc.body):
            if isinstance(s, N.Attr):
                row, col = s.obj, s.attr
                break
        if pol.deny_reveal:
            private = sorted(pol.deny_reveal)[0][1]
        t = rng.choice(_EDITS)
        return t.replace("ROW", row).replace("COL", col).replace("PRIVATE", private)

    def decide(req: ApprovalRequest) -> Decision:
        b = behavior if behavior != "random" else rng.choice(["approve", "deny", "timeout", "edit"])
        if b == "timeout":
            return Decision("approve", delay=req.timeout + timedelta(minutes=1))
        if b == "edit" and req.kind != "money" and rng.random() < 0.7:
            return Decision("edit", new_text=edit_text(req))
        if b == "edit":
            return Decision("approve")
        return Decision(b)

    return FromFunction(decide)


def _walk(x):
    yield x
    if isinstance(x, (tuple, list)):
        for y in x:
            yield from _walk(y)
    elif hasattr(x, "__dataclass_fields__"):
        for f in x.__dataclass_fields__:
            yield from _walk(getattr(x, f))


def run_case(name: str, seed: int, behavior: str, empty_rate: float) -> list[str]:
    """P1-P4, P7 (monitor), P8 (no blank slot delivered), P9 (edits)."""
    proc, policy = _example(name)
    rng = random.Random(seed)
    ws = workspace_for(proc, rng=rng, rows=rng.randint(0, 9), empty_rate=empty_rate)
    if isinstance(proc.trigger, N.NewRow) and not ws.row_ids(proc.trigger.sheet):
        return []
    from checker.policy import build_model
    pol = build_model(policy)
    # Private text cells get unique markers, so any appearance in a sent message is a real leak
    markers: set[str] = set()
    for sheet_alias, col in pol.deny_reveal:
        sheet = ws.sheets.get(sheet_alias)
        if sheet is None or sheet.columns.get(col) != "Text":
            continue
        for rid, row in sheet.rows.items():
            if row.get(col) is not EMPTY:
                row[col] = f"PRIVATE-{rng.getrandbits(48):012x}"
                markers.add(row[col])
    out = run_monitored(proc, policy, ws, provider(behavior, rng, proc, policy), params={"days": rng.randint(0, 90)})
    problems = list(out.problems)
    for e in ws.connector_log:
        if e["kind"] == "deliver":
            if "(blank)" in e["body"] or (e["subject"] and "(blank)" in e["subject"]):
                problems.append("P8 delivered a message with a blank slot")
            if "{" in e["body"]:
                problems.append("P9 raw placeholder delivered")
    # P9: private column values never appear in delivered text (also covers edits adding them)
    for e in ws.connector_log:
        if e["kind"] == "deliver":
            text = f"{e['subject'] or ''}\n{e['body']}"
            if any(m in text for m in markers):
                problems.append("P9 private value delivered")
    return problems


TAMPER = ["none", "name", "phone", "delete_row", "expire"]


def batch_tamper_case(seed: int, kind: str) -> list[str]:
    """P5: any change after a batch approval means nothing is delivered."""
    proc, policy = _example("AppointmentRemindersBatch")
    rng = random.Random(seed)
    now = workspace_for(proc).now
    n = rng.randint(1, 6)
    rows = [{"patient": f"P{i}", "phone": f"+1555100{i:04d}", "starts": now + timedelta(days=1, hours=1),
             "status": "booked", "reason": "r"} for i in range(n)]
    ws = workspace_for(proc, data={"Appointments": rows})
    target = rng.choice(ws.row_ids("Appointments"))

    def tamper():  # an outside human edit, so it bypasses the connector log on purpose
        row = ws.sheets["Appointments"].rows.get(target)
        if kind == "name":
            row["patient"] = "Changed"
        elif kind == "phone":
            row["phone"] = "+15559999999"
        elif kind == "delete_row":
            del ws.sheets["Appointments"].rows[target]
        elif kind == "expire":
            ws.now += timedelta(hours=1, minutes=1)

    out = run_monitored(proc, policy, ws, FromFunction(lambda req: Decision("approve", after=tamper)))
    sent = sum(1 for e in ws.connector_log if e["kind"] == "deliver")
    problems = list(out.problems)
    if kind == "none" and sent != n:
        problems.append(f"P5 untampered batch sent {sent} of {n}")
    if kind != "none":
        want = "X101" if kind == "expire" else "X102"
        if sent:
            problems.append(f"P5 tampered batch ({kind}) delivered {sent} messages")
        if not out.result.reason.startswith(want):
            problems.append(f"P5 tamper {kind}: expected {want}, got {out.result.reason[:40]}")
    return problems


def policy_case(seed: int) -> list[str]:
    """P6: random caps/thresholds; bad policies rejected, accepted ones keep every action in bounds."""
    rng = random.Random(seed)
    act = rng.choice([None, "5", "15", "50", "80", "5000"])
    day = rng.choice([None, "20", "300", "100000"])
    auto = rng.choice([None, "10", "15", "60", "5000"])
    src = block_defining("ProcessReturn")
    for old, new in (("  limit refund $50 per action\n", f"  limit refund ${act} per action\n" if act else ""),
                     ("  limit refund $300 per day\n", f"  limit refund ${day} per day\n" if day else ""),
                     ("  refund without approval up to $15\n", f"  refund without approval up to ${auto}\n" if auto else "")):
        src = src.replace(old, new)
    parsed = parse_source(src)
    proc, policy = parsed.procedures["ProcessReturn"], parsed.policies["ShopPolicy"]
    found = codes(errors(check(proc, policy)))
    problems = []
    if (act is None or day is None) and "E701" not in found:
        problems.append(f"P6 missing cap accepted (act={act}, day={day})")
    a, d, t = (Decimal(x) if x else None for x in (act, day, auto))
    if t is not None and a is not None and t > a and "E702" not in found:
        problems.append(f"P6 threshold {t} above cap {a} accepted")
    if a is not None and d is not None and a > d and "E702" not in found:
        problems.append(f"P6 per-action {a} above per-day {d} accepted")
    if found:
        return problems
    for i in range(3):
        ws = workspace_for(proc, rng=random.Random(seed * 10 + i), rows=1)
        out = run_monitored(proc, policy, ws, provider("random", rng, proc, policy))
        problems += out.problems
    return problems
