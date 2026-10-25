"""Batch approval helpers (SPEC.md section 6.1): render, fingerprint, preview, edit checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from checker import nodes as N
from checker.parser import AetherSyntaxError, parse_message
from checker.policy import PolicyModel

from .approvals import Item, h
from .evaluator import Evaluator, Rendered
from .values import EMPTY, DraftValue, Money, RowRef


@dataclass
class RenderedMessage:
    row: RowRef | None
    draft: DraftValue
    rendered: Rendered


def render_message(ev: Evaluator, msg: N.Message, env: dict) -> RenderedMessage:
    to = ev.eval(msg.to, env)
    body = ev.render(msg.body, env)
    subject = ev.render(msg.subject, env) if msg.subject is not None else None
    missing = list(body.missing) + (list(subject.missing) if subject else [])
    if to is EMPTY:
        missing.insert(0, "recipient")
    merged = Rendered(body.text, missing, body.defaults_used or bool(subject and subject.defaults_used),
                      body.values + (subject.values if subject else []))
    draft = DraftValue(msg.channel, to, subject.text if subject else None, body.text, missing)
    return RenderedMessage(None, draft, merged)


def render_batch(ev: Evaluator, msg: N.Message, var: str, rows: list[RowRef], scope: dict) -> list[RenderedMessage]:
    out = []
    for r in rows:
        rm = render_message(ev, msg, {**scope, var: r})
        rm.row = r
        out.append(rm)
    return out


def template_hash(msg: N.Message) -> str:
    return h(msg.channel, repr(msg.to), msg.subject.raw if msg.subject else None, msg.body.raw)


def recipients_hash(msgs: list[RenderedMessage]) -> str:
    return h([(m.row.row_id if m.row else None, str(m.draft.to)) for m in msgs])


def messages_hash(msgs: list[RenderedMessage]) -> str:
    return h([m.draft.text() for m in msgs])


def items(msgs: list[RenderedMessage]) -> list[Item]:
    return [Item(str(m.draft.to), m.draft.text()) for m in msgs]


def select_preview(msgs: list[RenderedMessage], k: int) -> list[int]:
    """Deterministic preview indexes: required edge cases first, then evenly spaced fill."""
    n = len(msgs)
    if n <= k:
        return list(range(n))
    picks: list[int] = [0, n - 1]
    lengths = [len(m.draft.text()) for m in msgs]
    picks += [lengths.index(max(lengths)), lengths.index(min(lengths))]
    picks += [i for i, m in enumerate(msgs) if m.rendered.defaults_used]
    slots = max(len(m.rendered.values) for m in msgs)
    for s in range(slots):
        vals = [(m.rendered.values[s], i) for i, m in enumerate(msgs)
                if s < len(m.rendered.values) and isinstance(m.rendered.values[s], (Decimal, Money, date))]
        if len(vals) == len(msgs) and vals:
            try:
                picks += [min(vals)[1], max(vals)[1]]
            except TypeError:
                pass
    seen: dict[str, int] = {}
    for i, m in enumerate(msgs):
        to = str(m.draft.to)
        if to in seen:
            picks += [seen[to], i]
        seen.setdefault(to, i)
    out = list(dict.fromkeys(picks))
    step = n / k
    j = 0
    while len(out) < k and j < k:
        idx = int(j * step)
        if idx not in out:
            out.append(idx)
        j += 1
    return sorted(out)


def check_edit(text: str, env: dict, policy: PolicyModel, allowed_rows: set[str]) -> tuple[N.Str | None, str]:
    """An owner edit may only interpolate `{row.col}` of rows in scope, readable and not private.

    Returns (parsed text, "") or (None, error code + reason).
    """
    try:
        s = parse_message(text)
    except AetherSyntaxError as exc:
        return None, f"E601 {exc}"
    for p in s.parts:
        if not isinstance(p, N.Interp):
            continue
        e = p.expr
        if not isinstance(e, N.Attr) or e.obj not in allowed_rows or not isinstance(env.get(e.obj), RowRef):
            return None, "E601 edits may only use {row.column} placeholders"
        sheet = env[e.obj].sheet
        if (sheet, e.attr) in policy.deny_reveal:
            return None, f"E301 {sheet}.{e.attr} is private"
        if e.attr not in policy.reads.get(sheet, set()):
            return None, f"E401 {sheet}.{e.attr} is not readable"
    return s, ""
