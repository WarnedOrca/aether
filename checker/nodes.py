"""Syntax tree for Aether programs and policies (SPEC.md sections 2-5).

Every node is an immutable dataclass with the source line, so diagnostics can
point at the exact statement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Union

# ---------- expressions


@dataclass(frozen=True)
class Num:
    value: Decimal
    line: int = 0


@dataclass(frozen=True)
class MoneyLit:
    value: Decimal
    line: int = 0


@dataclass(frozen=True)
class BoolLit:
    value: bool
    line: int = 0


@dataclass(frozen=True)
class DurationLit:
    amount: Decimal
    unit: str  # minute | hour | day | week
    line: int = 0


@dataclass(frozen=True)
class Interp:
    expr: "Expr"
    default: str | None


@dataclass(frozen=True)
class Str:
    """A double-quoted string. `parts` alternates literal text and Interp."""

    raw: str
    parts: tuple[Union[str, Interp], ...]
    line: int = 0


@dataclass(frozen=True)
class Name:
    name: str
    line: int = 0


@dataclass(frozen=True)
class Attr:
    obj: str
    attr: str
    line: int = 0


@dataclass(frozen=True)
class Call:
    func: str
    args: tuple["Expr", ...]
    line: int = 0


@dataclass(frozen=True)
class BinOp:
    op: str  # + - * / == != < <= > >= and or
    left: "Expr"
    right: "Expr"
    line: int = 0


@dataclass(frozen=True)
class Not:
    expr: "Expr"
    line: int = 0


Expr = Union[Num, MoneyLit, BoolLit, DurationLit, Str, Name, Attr, Call, BinOp, Not]

# ---------- right-hand sides of `let`


@dataclass(frozen=True)
class ElseSkip:
    line: int = 0


@dataclass(frozen=True)
class ElseStop:
    reason: Str
    line: int = 0


Else = Union[ElseSkip, ElseStop]


@dataclass(frozen=True)
class Fetch:
    sheet: str
    line: int = 0


@dataclass(frozen=True)
class Filter:
    table: str
    cond: Expr
    line: int = 0


@dataclass(frozen=True)
class Sort:
    table: str
    col: str
    desc: bool
    first: int | None
    line: int = 0


@dataclass(frozen=True)
class Find:
    table: str
    cond: Expr
    els: Else
    line: int = 0


@dataclass(frozen=True)
class Summarize:
    agg: str  # count sum avg min max
    col: str | None
    table: str
    line: int = 0


@dataclass(frozen=True)
class Message:
    channel: str  # sms | email
    to: Expr
    subject: Str | None
    body: Str


@dataclass(frozen=True)
class Draft:
    msg: Message
    line: int = 0


@dataclass(frozen=True)
class DraftEach:
    var: str
    table: str
    bound: int | None
    msg: Message
    line: int = 0


@dataclass(frozen=True)
class Approve:
    draft: str
    timeout: DurationLit
    els: Else
    batch: bool
    line: int = 0


@dataclass(frozen=True)
class Book:
    calendar: str
    fields: tuple[tuple[str, Expr], ...]
    line: int = 0


Rhs = Union[Fetch, Filter, Sort, Find, Summarize, Draft, DraftEach, Approve, Book, Expr]

# ---------- statements


@dataclass(frozen=True)
class Let:
    name: str
    rhs: Rhs
    line: int = 0


@dataclass(frozen=True)
class Append:
    sheet: str
    fields: tuple[tuple[str, Expr], ...]
    line: int = 0


@dataclass(frozen=True)
class Update:
    row: str
    assigns: tuple[tuple[str, Expr], ...]
    line: int = 0


@dataclass(frozen=True)
class Send:
    name: str
    line: int = 0


@dataclass(frozen=True)
class Notify:
    text: Str
    line: int = 0


@dataclass(frozen=True)
class Cancel:
    calendar: str
    event_id: Expr
    line: int = 0


@dataclass(frozen=True)
class Wait:
    duration: DurationLit
    line: int = 0


@dataclass(frozen=True)
class Ask:
    timeout: DurationLit
    els: Else


@dataclass(frozen=True)
class Refund:
    amount: Expr
    ident: Expr
    reason: Str
    ask: Ask | None
    line: int = 0


@dataclass(frozen=True)
class Order:
    what: Str
    supplier: Expr
    cost: Expr
    ask: Ask | None
    line: int = 0


@dataclass(frozen=True)
class If:
    cond: Expr
    then: tuple["Stmt", ...]
    els: tuple["Stmt", ...] | None
    line: int = 0


@dataclass(frozen=True)
class ForEach:
    var: str
    table: str
    bound: int | None
    body: tuple["Stmt", ...]
    line: int = 0


@dataclass(frozen=True)
class Stop:
    reason: Str
    line: int = 0


@dataclass(frozen=True)
class Skip:
    line: int = 0


@dataclass(frozen=True)
class Log:
    text: Str
    line: int = 0


Stmt = Union[Let, Append, Update, Send, Notify, Cancel, Wait, Refund, Order, If, ForEach, Stop, Skip, Log]

# ---------- program structure


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    private: bool


@dataclass(frozen=True)
class Sheet:
    alias: str
    title: str
    columns: dict[str, Column]


@dataclass(frozen=True)
class Every:
    kind: str  # daily | weekly | monthly | interval
    time: str | None = None
    weekday: str | None = None
    day_of_month: int | None = None
    interval: DurationLit | None = None


@dataclass(frozen=True)
class NewRow:
    var: str
    sheet: str


@dataclass(frozen=True)
class Requested:
    params: tuple[tuple[str, str], ...]


Trigger = Union[Every, NewRow, Requested]


@dataclass(frozen=True)
class Procedure:
    name: str
    about: str
    policy: str
    sheets: dict[str, Sheet]
    calendars: dict[str, str]
    trigger: Trigger
    body: tuple[Stmt, ...]
    line: int = 0


# ---------- policies


@dataclass(frozen=True)
class Rule:
    kind: str
    args: tuple
    line: int = 0
    text: str = ""


@dataclass(frozen=True)
class PolicyLineError:
    text: str
    line: int


@dataclass(frozen=True)
class Policy:
    name: str
    rules: tuple[Rule, ...]
    bad_lines: tuple[PolicyLineError, ...] = field(default=())
    line: int = 0


@dataclass(frozen=True)
class SourceFile:
    policies: dict[str, Policy]
    procedures: dict[str, Procedure]
