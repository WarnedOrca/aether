"""Parse Aether source text into the syntax tree in nodes.py.

Public functions:
    parse_source(text) -> SourceFile      (policies + procedures in one file)
    parse_message(raw, line) -> Str       (split a message string into text and {interp})
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from lark import Lark, Token, Transformer, Tree, v_args
from lark.exceptions import LarkError

from . import nodes as N

_GRAMMAR = (Path(__file__).parent / "grammar.lark").read_text(encoding="utf-8")


class AetherSyntaxError(ValueError):
    """Raised when source text does not match the grammar."""

    def __init__(self, message: str, line: int = 0):
        super().__init__(f"line {line}: {message}" if line else message)
        self.line = line


@lru_cache(maxsize=1)
def _lark() -> Lark:
    return Lark(
        _GRAMMAR,
        start=["start", "prule", "interp"],
        parser="lalr",
        lexer="contextual",
        propagate_positions=True,
        maybe_placeholders=True,
    )


def _line(meta) -> int:
    return getattr(meta, "line", 0) or 0


def _unit(text: str) -> str:
    return text.rstrip("s") if text != "s" else text


def _money(tok: str) -> Decimal:
    return Decimal(tok[1:])


def _strip_quotes(tok: str) -> str:
    return tok[1:-1]


_INTERP = re.compile(r"\{([^{}]*)\}")


def parse_message(raw: str, line: int = 0) -> N.Str:
    """Split `raw` (without quotes) into literal text and parsed interpolations."""
    parts: list = []
    pos = 0
    for m in _INTERP.finditer(raw):
        if m.start() > pos:
            parts.append(raw[pos:m.start()])
        try:
            tree = _lark().parse(m.group(1), start="interp")
        except LarkError as exc:
            raise AetherSyntaxError(f"bad interpolation {{{m.group(1)}}}: {exc}", line) from exc
        expr_tree, default_tok = tree.children
        expr = _ToAst(line, fixed=True).transform(expr_tree)
        default = _strip_quotes(str(default_tok)) if default_tok is not None else None
        parts.append(N.Interp(expr, default))
        pos = m.end()
    if pos < len(raw):
        parts.append(raw[pos:])
    leftover = _INTERP.sub("", raw)
    if "{" in leftover or "}" in leftover:
        raise AetherSyntaxError("unbalanced braces in message", line)
    return N.Str(raw, tuple(parts), line)


@v_args(meta=True)
class _ToAst(Transformer):
    """Turns Lark trees into nodes.py dataclasses."""

    def __init__(self, base_line: int = 0, fixed: bool = False):
        super().__init__()
        self._base = base_line
        self._fixed = fixed  # inside a message string: report the string's own line

    def _ln(self, meta) -> int:
        if self._fixed:
            return self._base
        return _line(meta) or self._base

    # ----- expressions
    def number(self, meta, c):
        return N.Num(Decimal(str(c[0])), self._ln(meta))

    def money(self, meta, c):
        return N.MoneyLit(_money(str(c[0])), self._ln(meta))

    def string(self, meta, c):
        return parse_message(_strip_quotes(str(c[0])), self._ln(meta))

    def true(self, meta, c):
        return N.BoolLit(True, self._ln(meta))

    def false(self, meta, c):
        return N.BoolLit(False, self._ln(meta))

    def duration_lit(self, meta, c):
        return N.DurationLit(Decimal(str(c[0])), _unit(str(c[1])), self._ln(meta))

    def duration(self, meta, c):
        return N.DurationLit(Decimal(str(c[0])), _unit(str(c[1])), self._ln(meta))

    def call(self, meta, c):
        args = tuple(a for a in c[1:] if a is not None)
        return N.Call(str(c[0]), args, self._ln(meta))

    def attr(self, meta, c):
        return N.Attr(str(c[0]), str(c[1]), self._ln(meta))

    def name(self, meta, c):
        return N.Name(str(c[0]), self._ln(meta))

    def or_(self, meta, c):
        return N.BinOp("or", c[0], c[1], self._ln(meta))

    def and_(self, meta, c):
        return N.BinOp("and", c[0], c[1], self._ln(meta))

    def not_(self, meta, c):
        return N.Not(c[0], self._ln(meta))

    def compare(self, meta, c):
        return N.BinOp(str(c[1]), c[0], c[2], self._ln(meta))

    def binop(self, meta, c):
        return N.BinOp(str(c[1]), c[0], c[2], self._ln(meta))

    # ----- else / ask
    def else_skip(self, meta, c):
        return N.ElseSkip(self._ln(meta))

    def else_stop(self, meta, c):
        return N.ElseStop(self._str(c[0], meta), self._ln(meta))

    def ask(self, meta, c):
        return N.Ask(c[0], c[1])

    def _str(self, tok, meta) -> N.Str:
        if isinstance(tok, N.Str):
            return tok
        return parse_message(_strip_quotes(str(tok)), self._ln(meta))

    # ----- rhs
    def fetch(self, meta, c):
        return N.Fetch(str(c[0]), self._ln(meta))

    def filter(self, meta, c):
        return N.Filter(str(c[0]), c[1], self._ln(meta))

    def sort(self, meta, c):
        first = int(str(c[3])) if c[3] is not None else None
        return N.Sort(str(c[0]), str(c[1]), c[2] is not None, first, self._ln(meta))

    def find(self, meta, c):
        return N.Find(str(c[0]), c[1], c[2], self._ln(meta))

    def summarize(self, meta, c):
        col = str(c[1]) if c[1] is not None else None
        return N.Summarize(str(c[0]), col, str(c[2]), self._ln(meta))

    def sms(self, meta, c):
        return N.Message("sms", c[0], None, self._str(c[1], meta))

    def email(self, meta, c):
        return N.Message("email", c[0], self._str(c[1], meta), self._str(c[2], meta))

    def draft(self, meta, c):
        return N.Draft(c[0], self._ln(meta))

    def draft_each(self, meta, c):
        bound = int(str(c[2])) if c[2] is not None else None
        return N.DraftEach(str(c[0]), str(c[1]), bound, c[3], self._ln(meta))

    def approve(self, meta, c):
        return N.Approve(str(c[0]), c[1], c[2], False, self._ln(meta))

    def approve_batch(self, meta, c):
        return N.Approve(str(c[0]), c[1], c[2], True, self._ln(meta))

    def field(self, meta, c):
        return (str(c[0]), c[1])

    def assign(self, meta, c):
        return (str(c[0]), c[1])

    def book(self, meta, c):
        return N.Book(str(c[0]), tuple(c[1:]), self._ln(meta))

    # ----- statements
    def let_stmt(self, meta, c):
        return N.Let(str(c[0]), c[1], self._ln(meta))

    def append_stmt(self, meta, c):
        return N.Append(str(c[0]), tuple(c[1:]), self._ln(meta))

    def update_stmt(self, meta, c):
        return N.Update(str(c[0]), tuple(c[1:]), self._ln(meta))

    def send_stmt(self, meta, c):
        return N.Send(str(c[0]), self._ln(meta))

    def notify_stmt(self, meta, c):
        return N.Notify(self._str(c[0], meta), self._ln(meta))

    def cancel_stmt(self, meta, c):
        return N.Cancel(str(c[0]), c[1], self._ln(meta))

    def wait_stmt(self, meta, c):
        return N.Wait(c[0], self._ln(meta))

    def refund_stmt(self, meta, c):
        return N.Refund(c[0], c[1], self._str(c[2], meta), c[3], self._ln(meta))

    def order_stmt(self, meta, c):
        return N.Order(self._str(c[0], meta), c[1], c[2], c[3], self._ln(meta))

    def block(self, meta, c):
        return tuple(c)

    def if_stmt(self, meta, c):
        return N.If(c[0], c[1], c[2], self._ln(meta))

    def for_stmt(self, meta, c):
        bound = int(str(c[2])) if c[2] is not None else None
        return N.ForEach(str(c[0]), str(c[1]), bound, c[3], self._ln(meta))

    def stop_stmt(self, meta, c):
        return N.Stop(self._str(c[0], meta), self._ln(meta))

    def skip_stmt(self, meta, c):
        return N.Skip(self._ln(meta))

    def log_stmt(self, meta, c):
        return N.Log(self._str(c[0], meta), self._ln(meta))

    # ----- declarations and triggers
    def col(self, meta, c):
        return N.Column(str(c[0]), str(c[1]), len(c) > 2 and c[2] is not None)

    def sheet(self, meta, c):
        cols = {col.name: col for col in c[2:]}
        return N.Sheet(str(c[0]), _strip_quotes(str(c[1])), cols)

    def calendar(self, meta, c):
        return ("calendar", str(c[0]), _strip_quotes(str(c[1])))

    def sch_daily(self, meta, c):
        return N.Every("daily", time=str(c[0]))

    def sch_weekly(self, meta, c):
        return N.Every("weekly", time=str(c[1]), weekday=str(c[0]))

    def sch_monthly(self, meta, c):
        return N.Every("monthly", time=str(c[1]), day_of_month=int(str(c[0])))

    def sch_interval(self, meta, c):
        return N.Every("interval", interval=N.DurationLit(Decimal(str(c[0])), _unit(str(c[1]))))

    def trig_every(self, meta, c):
        return c[0]

    def trig_row(self, meta, c):
        return N.NewRow(str(c[0]), str(c[1]))

    def param(self, meta, c):
        return (str(c[0]), str(c[1]))

    def trig_requested(self, meta, c):
        return N.Requested(tuple(p for p in c if p is not None))

    def procedure(self, meta, c):
        name, about, policy = str(c[0]), parse_message(_strip_quotes(str(c[1]))).raw, str(c[2])
        sheets: dict[str, N.Sheet] = {}
        calendars: dict[str, str] = {}
        trigger = None
        body: list = []
        for item in c[3:]:
            if isinstance(item, N.Sheet):
                sheets[item.alias] = item
            elif isinstance(item, tuple) and item and item[0] == "calendar":
                calendars[item[1]] = item[2]
            elif isinstance(item, (N.Every, N.NewRow, N.Requested)) and trigger is None:
                trigger = item
            else:
                body.append(item)
        return N.Procedure(name, about, policy, sheets, calendars, trigger, tuple(body), self._ln(meta))

    def policy(self, meta, c):
        return _parse_policy_body(str(c[0]), str(c[1]), self._ln(meta))

    def start(self, meta, c):
        return list(c)


@v_args(meta=True)
class _PolicyRule(Transformer):
    def names(self, meta, c):
        return tuple(str(x) for x in c)

    def colref(self, meta, c):
        return (str(c[0]), str(c[1]))

    def duration(self, meta, c):
        return N.DurationLit(Decimal(str(c[0])), _unit(str(c[1])))

    def __default__(self, data, children, meta):
        args = []
        for ch in children:
            if isinstance(ch, Token):
                if ch.type == "MONEY":
                    args.append(_money(str(ch)))
                elif ch.type == "INT":
                    args.append(int(str(ch)))
                elif ch.type == "STRING":
                    args.append(_strip_quotes(str(ch)))
                else:
                    args.append(str(ch))
            else:
                args.append(ch)
        return N.Rule(str(data), tuple(args))


def _parse_policy_body(name: str, body: str, start_line: int) -> N.Policy:
    rules: list[N.Rule] = []
    bad: list[N.PolicyLineError] = []
    for offset, raw in enumerate(body[1:-1].split("\n")):
        text = raw.split("#", 1)[0].strip()
        if not text:
            continue
        line = start_line + offset
        try:
            tree = _lark().parse(text, start="prule")
            rule = _PolicyRule().transform(tree)
            rules.append(N.Rule(rule.kind, rule.args, line, text))
        except LarkError:
            bad.append(N.PolicyLineError(text, line))
    return N.Policy(name, tuple(rules), tuple(bad), start_line)


def parse_source(text: str) -> N.SourceFile:
    """Parse a file that may hold several policies and procedures."""
    try:
        tree: Tree = _lark().parse(text, start="start")
    except LarkError as exc:
        line = getattr(exc, "line", 0) or 0
        raise AetherSyntaxError(str(exc).splitlines()[0], line) from exc
    items = _ToAst().transform(tree)
    policies = {p.name: p for p in items if isinstance(p, N.Policy)}
    procedures = {p.name: p for p in items if isinstance(p, N.Procedure)}
    for proc in procedures.values():
        if proc.trigger is None:
            raise AetherSyntaxError(f"procedure {proc.name} has no trigger", proc.line)
    return N.SourceFile(policies, procedures)
