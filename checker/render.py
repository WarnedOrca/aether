"""Deterministic plain-English rendering of a checked program (SPEC.md section 9).

Template-based on purpose: no model is involved, so the rendering cannot invent
a friendlier description than what the program does.
"""

from __future__ import annotations

from . import nodes as N
from .check import check
from .policy import build_model

_CMP = {"==": "is", "!=": "is not", "<": "is less than", "<=": "is at most", ">": "is more than", ">=": "is at least"}


def expr(e) -> str:
    if isinstance(e, N.Num):
        return f"{e.value.normalize():f}"
    if isinstance(e, N.MoneyLit):
        return f"${e.value:,.2f}"
    if isinstance(e, N.BoolLit):
        return "yes" if e.value else "no"
    if isinstance(e, N.DurationLit):
        n = f"{e.amount.normalize():f}"
        return f"{n} {e.unit}" + ("" if n == "1" else "s")
    if isinstance(e, N.Str):
        return f"\"{text(e)}\""
    if isinstance(e, N.Name):
        return e.name.replace("_", " ")
    if isinstance(e, N.Attr):
        return e.attr.replace("_", " ")
    if isinstance(e, N.Not):
        return f"not ({expr(e.expr)})"
    if isinstance(e, N.Call):
        a = [expr(x) for x in e.args]
        return {
            "today": lambda: "today",
            "now": lambda: "now",
            "date_of": lambda: f"the date of {a[0]}",
            "time_of": lambda: f"the time of {a[0]}",
            "days_between": lambda: f"the days from {a[0]} to {a[1]}",
            "min": lambda: f"the smaller of {a[0]} and {a[1]}",
            "max": lambda: f"the larger of {a[0]} and {a[1]}",
            "round": lambda: f"{a[0]} rounded",
            "lower": lambda: f"{a[0]} in lowercase",
            "contains": lambda: f"{a[0]} contains {a[1]}",
            "is_empty": lambda: f"{a[0]} is blank",
        }.get(e.func, lambda: f"{e.func}({', '.join(a)})")()
    if isinstance(e, N.BinOp):
        op = _CMP.get(e.op, e.op)
        return f"{expr(e.left)} {op} {expr(e.right)}"
    return "?"


def text(s: N.Str) -> str:
    out = []
    for p in s.parts:
        if isinstance(p, str):
            out.append(p)
        else:
            slot = expr(p.expr)
            out.append(f"{{{slot}, or '{p.default}' if blank}}" if p.default is not None else f"{{{slot}}}")
    return "".join(out)


def _else(els) -> str:
    return "move on to the next one" if isinstance(els, N.ElseSkip) else f"stop ({text(els.reason)})"


def _trigger(t) -> str:
    if isinstance(t, N.NewRow):
        return f"This runs when a new row is added to {t.sheet}."
    if isinstance(t, N.Requested):
        ps = ", ".join(f"{n} ({ty})" for n, ty in t.params)
        return "This runs when you ask for it" + (f", giving: {ps}." if ps else ".")
    if t.kind == "daily":
        return f"This runs every day at {t.time}."
    if t.kind == "weekly":
        return f"This runs every {t.weekday.capitalize()} at {t.time}."
    if t.kind == "monthly":
        return f"This runs on day {t.day_of_month} of every month at {t.time}."
    return f"This runs every {expr(t.interval)}."


def _rhs(r, name: str) -> str:
    if isinstance(r, N.Fetch):
        return f"Read all rows from {r.sheet}."
    if isinstance(r, N.Filter):
        return f"Keep only rows where {expr(r.cond)} (call them {name})."
    if isinstance(r, N.Sort):
        tail = (", newest/largest first" if r.desc else "") + (f", keep the first {r.first}" if r.first else "")
        return f"Sort {r.table} by {r.col.replace('_', ' ')}{tail}."
    if isinstance(r, N.Find):
        return f"Find the row in {r.table} where {expr(r.cond)}; if none, {_else(r.els)}."
    if isinstance(r, N.Summarize):
        what = {"count": "number of rows", "sum": "total", "avg": "average", "min": "smallest", "max": "largest"}[r.agg]
        col = f" {r.col.replace('_', ' ')}" if r.col else ""
        return f"Work out the {what}{col} in {r.table} (call it {name})."
    if isinstance(r, N.Draft):
        return _msg(r.msg, "")
    if isinstance(r, N.DraftEach):
        return _msg(r.msg, f" each of up to {r.bound}")
    if isinstance(r, N.Approve):
        if r.batch:
            return (f"Show you sample messages, including unusual ones, and ask you to approve all of them at once "
                    f"(you may approve, deny, or edit; an edit shows them again). The approval covers only exactly "
                    f"these messages. Wait up to {expr(r.timeout)}. If not approved, {_else(r.els)}.")
        return (f"Ask you to approve this message (you may approve, deny, or edit; an edit shows it again). "
                f"Wait up to {expr(r.timeout)}. If not approved, {_else(r.els)}.")
    if isinstance(r, N.Book):
        f = dict(r.fields)
        return f"Add {expr(f['title'])} to the {r.calendar} calendar at {expr(f['at'])}."
    return f"Work out {name} = {expr(r)}."


def _msg(m: N.Message, each: str) -> str:
    kind = "a text" if m.channel == "sms" else "an email"
    subj = f" with subject \"{text(m.subject)}\"" if m.subject else ""
    return f"Write {kind}{each} to {expr(m.to)}{subj}: \"{text(m.body)}\""


def _ask(a) -> str:
    return f" after you approve (wait up to {expr(a.timeout)}; if not approved, {_else(a.els)})"


def _stmt(s, depth: int, out: list[str]) -> None:
    pad = "   " * depth + "- "
    if isinstance(s, N.Let):
        out.append(pad + _rhs(s.rhs, s.name))
    elif isinstance(s, N.Send):
        out.append(pad + "Send the approved message(s); if anything changed since approval, send nothing.")
    elif isinstance(s, N.Notify):
        out.append(pad + f"Tell you (not the customer): \"{text(s.text)}\"")
    elif isinstance(s, N.Log):
        out.append(pad + f"Write to the log: \"{text(s.text)}\"")
    elif isinstance(s, N.Update):
        sets = ", ".join(f"{c.replace('_', ' ')} to {expr(e)}" for c, e in s.assigns)
        out.append(pad + f"On that row, set {sets}.")
    elif isinstance(s, N.Append):
        cols = ", ".join(f"{c} = {expr(e)}" for c, e in s.fields)
        out.append(pad + f"Add a row to {s.sheet}: {cols}.")
    elif isinstance(s, N.Cancel):
        out.append(pad + f"Remove event {expr(s.event_id)} from the {s.calendar} calendar.")
    elif isinstance(s, N.Wait):
        out.append(pad + f"Wait {expr(s.duration)}.")
    elif isinstance(s, N.Refund):
        how = _ask(s.ask) if s.ask else " without asking, because it is within your auto-refund limit"
        out.append(pad + f"Refund {expr(s.amount)} for {expr(s.ident)}{how}.")
    elif isinstance(s, N.Order):
        out.append(pad + f"Order {expr(s.what)} from {expr(s.supplier)} for {expr(s.cost)}{_ask(s.ask) if s.ask else ''}.")
    elif isinstance(s, N.Stop):
        out.append(pad + f"Stop here ({text(s.reason)}).")
    elif isinstance(s, N.Skip):
        out.append(pad + "Move on to the next one.")
    elif isinstance(s, N.If):
        out.append(pad + f"If {expr(s.cond)}:")
        for x in s.then:
            _stmt(x, depth + 1, out)
        if s.els:
            out.append("   " * depth + "- Otherwise:")
            for x in s.els:
                _stmt(x, depth + 1, out)
    elif isinstance(s, N.ForEach):
        out.append(pad + f"For each row in {s.table}, at most {s.bound} of them:")
        for x in s.body:
            _stmt(x, depth + 1, out)


def safety_summary(proc: N.Procedure, policy: N.Policy) -> list[str]:
    m = build_model(policy)
    lines = []
    if m.mode == "batch":
        lines.append(f"Approval: batch (valid {m.batch_valid}, at most {m.batch_max} messages, "
                     f"at least {m.batch_preview} samples shown).")
    else:
        lines.append("Approval: per message. Every message needs your approval.")
    for op in ("refund", "order"):
        act, day = m.money_cap(op, "action"), m.money_cap(op, "day")
        if act is not None or day is not None:
            auto = ""
            if op == "refund":
                auto = (f"Refunds over ${m.auto_refund:,.2f} need your OK; " if m.auto_refund is not None
                        else "Every refund needs your OK; ")
            else:
                auto = "Every order needs your OK; "
            lines.append(f"{auto}no {op} over ${act:,.2f} ever; at most ${day:,.2f} per day.")
    for period, cap in sorted(m.sends.items()):
        lines.append(f"At most {cap} messages per {period}.")
    if m.window:
        lines.append(f"Messages only between {m.window[0]} and {m.window[1]}.")
    lines.append("Messages with a blank field and no default are not sent.")
    used = sorted({f"{s}.{c}" for s, cols in m.reads.items() if s in proc.sheets for c in cols})
    if used:
        lines.append("Can read: " + ", ".join(used) + ".")
    if m.deny_reveal:
        lines.append("Never put in a message: " + ", ".join(f"{s}.{c}" for s, c in sorted(m.deny_reveal)) + ".")
    for d in check(proc, policy):
        if d.code == "W201":
            lines.append(f"WARNING: large cap: {d.detail}.")
    return lines


def render(proc: N.Procedure, policy: N.Policy) -> str:
    out = [f"{proc.name} (policy: {proc.policy})", proc.about, _trigger(proc.trigger)]
    for s in proc.body:
        _stmt(s, 0, out)
    out.append("Safety summary:")
    out += ["  " + line for line in safety_summary(proc, policy)]
    return "\n".join(out)
