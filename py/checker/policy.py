"""Policy model and policy validation (SPEC.md section 5: E701-E704, W201)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from . import nodes as N
from .diagnostics import Diagnostic

# Untested defaults (SPEC.md section 5); judgment, not measurement.
BATCH_MAX_VALID = timedelta(hours=24)
BATCH_MIN_PREVIEW = 5
LARGE_MONEY_ACTION = Decimal("500")
LARGE_MONEY_DAY = Decimal("2000")
LARGE_SENDS = {"day": 500, "week": 2000}
LARGE_BATCH_MAX = 200
MAX_WAIT = timedelta(days=30)

_UNIT = {"minute": timedelta(minutes=1), "hour": timedelta(hours=1), "day": timedelta(days=1), "week": timedelta(weeks=1)}


def to_timedelta(d: N.DurationLit) -> timedelta:
    return _UNIT[d.unit] * float(d.amount)


@dataclass
class PolicyModel:
    name: str
    reads: dict[str, set[str]] = field(default_factory=dict)
    writes: dict[str, set[str]] = field(default_factory=dict)
    appends: set[str] = field(default_factory=set)
    contacts: set[tuple[str, str]] = field(default_factory=set)
    supplier_cols: set[tuple[str, str]] = field(default_factory=set)
    supplier_lits: set[str] = field(default_factory=set)
    calendars: set[str] = field(default_factory=set)
    deny_reveal: set[tuple[str, str]] = field(default_factory=set)
    money: dict[tuple[str, str], Decimal] = field(default_factory=dict)  # (refund|order, action|day)
    sends: dict[str, int] = field(default_factory=dict)  # day|week -> cap
    auto_refund: Decimal | None = None
    window: tuple[str, str] | None = None
    mode: str = "per_message"
    batch_valid: timedelta | None = None
    batch_max: int | None = None
    batch_preview: int | None = None
    bad_lines: tuple[N.PolicyLineError, ...] = ()
    rule_lines: dict[str, int] = field(default_factory=dict)

    def money_cap(self, op: str, period: str) -> Decimal | None:
        return self.money.get((op, period))


def _stricter(old, new):
    return new if old is None else min(old, new)


def build_model(policy: N.Policy) -> PolicyModel:
    """Duplicate limits keep the stricter (smaller) value."""
    m = PolicyModel(policy.name, bad_lines=policy.bad_lines)
    for r in policy.rules:
        a = r.args
        m.rule_lines.setdefault(r.kind, r.line)
        if r.kind == "allow_read":
            m.reads.setdefault(a[0], set()).update(a[1])
        elif r.kind == "allow_write":
            m.writes.setdefault(a[0], set()).update(a[1])
        elif r.kind == "allow_append":
            m.appends.add(a[0])
        elif r.kind == "allow_contact":
            m.contacts.add(a[0])
        elif r.kind == "allow_supplier_col":
            m.supplier_cols.add(a[0])
        elif r.kind == "allow_supplier_lit":
            m.supplier_lits.add(a[0])
        elif r.kind == "allow_calendar":
            m.calendars.add(a[0])
        elif r.kind == "deny_reveal":
            m.deny_reveal.add(a[0])
        elif r.kind == "limit_money":
            key = (a[0], a[2])
            m.money[key] = _stricter(m.money.get(key), a[1])
        elif r.kind == "limit_sends":
            m.sends[a[1]] = _stricter(m.sends.get(a[1]), a[0])
        elif r.kind == "auto_refund":
            m.auto_refund = _stricter(m.auto_refund, a[0])
        elif r.kind == "send_window":
            m.window = (a[0], a[1])
        elif r.kind == "approval_per_message":
            m.mode = "per_message"
        elif r.kind == "approval_batch":
            m.mode = "batch"
            m.batch_valid = to_timedelta(a[0])
            m.batch_max, m.batch_preview = a[1], a[2]
    return m


@dataclass(frozen=True)
class Usage:
    refund: bool = False
    order: bool = False
    send: bool = False
    batch: bool = False


def validate(m: PolicyModel, usage: Usage) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for bad in m.bad_lines:
        out.append(Diagnostic("E704", f"'{bad.text}'", bad.line))
    for op, used in (("refund", usage.refund), ("order", usage.order)):
        if not used:
            continue
        for period in ("action", "day"):
            if m.money_cap(op, period) is None:
                out.append(Diagnostic("E701", f"needs 'limit {op} $X per {period}'"))
    if usage.send and not m.sends:
        out.append(Diagnostic("E701", "needs 'limit sends N per day' (or per week)"))
    for op in ("refund", "order"):
        act, day = m.money_cap(op, "action"), m.money_cap(op, "day")
        if act is not None and day is not None and act > day:
            out.append(Diagnostic("E702", f"{op} per-action cap ${act} above per-day cap ${day}"))
    if m.auto_refund is not None:
        act = m.money_cap("refund", "action")
        if act is None:
            out.append(Diagnostic("E701", "auto-refund threshold needs a per-action refund cap"))
        elif m.auto_refund > act:
            out.append(Diagnostic("E702", f"auto-refund ${m.auto_refund} above per-action cap ${act}"))
    if m.mode == "batch":
        out.extend(_validate_batch(m))
    out.extend(_large_caps(m))
    return out


def _validate_batch(m: PolicyModel) -> list[Diagnostic]:
    out = []
    if m.batch_valid is None or m.batch_valid > BATCH_MAX_VALID or m.batch_valid <= timedelta(0):
        out.append(Diagnostic("E703", "batch 'valid' must be > 0 and <= 24 hours"))
    if m.batch_max is None or m.batch_max < 1:
        out.append(Diagnostic("E703", "batch 'max' must be at least 1"))
    elif m.batch_preview is None or m.batch_preview < min(BATCH_MIN_PREVIEW, m.batch_max):
        out.append(Diagnostic("E703", f"batch 'preview' must be >= min({BATCH_MIN_PREVIEW}, max)"))
    if m.batch_max is not None and m.sends:
        cap = min(m.sends.values())
        if m.batch_max > cap:
            out.append(Diagnostic("E703", f"batch 'max' {m.batch_max} above send cap {cap}"))
    return out


def _large_caps(m: PolicyModel) -> list[Diagnostic]:
    out = []
    for (op, period), cap in sorted(m.money.items()):
        ref = LARGE_MONEY_ACTION if period == "action" else LARGE_MONEY_DAY
        if period in ("action", "day") and cap > ref:
            out.append(Diagnostic("W201", f"{op} cap ${cap} per {period} (reference ${ref})"))
    for period, cap in sorted(m.sends.items()):
        if cap > LARGE_SENDS.get(period, LARGE_SENDS["day"]):
            out.append(Diagnostic("W201", f"send cap {cap} per {period} (reference {LARGE_SENDS[period]})"))
    if m.batch_max is not None and m.batch_max > LARGE_BATCH_MAX:
        out.append(Diagnostic("W201", f"batch max {m.batch_max} (reference {LARGE_BATCH_MAX})"))
    return out
