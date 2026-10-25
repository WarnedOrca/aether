"""Evaluate Aether expressions and render message strings at run time."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from checker import nodes as N

from .values import EMPTY, Money, RowRef, fmt
from .workspace import Workspace

_UNIT = {"minute": timedelta(minutes=1), "hour": timedelta(hours=1), "day": timedelta(days=1), "week": timedelta(weeks=1)}


class RuntimeFault(Exception):
    """A run-time error: the run stops and is logged (e.g. empty value in arithmetic)."""


class EmptyValueFault(RuntimeFault):
    """An empty cell reached a calculation or comparison."""


def duration(d: N.DurationLit) -> timedelta:
    return _UNIT[d.unit] * float(d.amount)


@dataclass
class Rendered:
    text: str
    missing: list[str] = field(default_factory=list)  # empty slots with no default
    defaults_used: bool = False
    values: list[Any] = field(default_factory=list)  # interpolated values, for previews


class Evaluator:
    def __init__(self, ws: Workspace, sheet_columns: dict[str, set[str]]):
        self.ws = ws
        self.sheet_columns = sheet_columns  # alias -> declared columns

    # ----- strings
    def render(self, s: N.Str, env: dict, row: RowRef | None = None) -> Rendered:
        out = Rendered("")
        pieces: list[str] = []
        for p in s.parts:
            if isinstance(p, str):
                pieces.append(p)
                continue
            v = self.eval(p.expr, env, row)
            if v is EMPTY:
                if p.default is not None:
                    pieces.append(p.default)
                    out.defaults_used = True
                else:
                    out.missing.append(_show(p.expr))
                    pieces.append("(blank)")
                continue
            out.values.append(v)
            pieces.append(fmt(v))
        out.text = "".join(pieces)
        return out

    # ----- expressions
    def eval(self, e: N.Expr, env: dict, row: RowRef | None = None) -> Any:
        if isinstance(e, N.Num):
            return e.value
        if isinstance(e, N.MoneyLit):
            return Money(e.value)
        if isinstance(e, N.BoolLit):
            return e.value
        if isinstance(e, N.DurationLit):
            return duration(e)
        if isinstance(e, N.Str):
            return self.render(e, env, row).text
        if isinstance(e, N.Name):
            if row is not None and e.name in self.sheet_columns.get(row.sheet, ()):
                return self.cell(row, e.name)
            if e.name not in env:
                raise RuntimeFault(f"unknown name {e.name}")
            return env[e.name]
        if isinstance(e, N.Attr):
            r = env.get(e.obj)
            if not isinstance(r, RowRef):
                raise RuntimeFault(f"{e.obj} is not a row")
            return self.cell(r, e.attr)
        if isinstance(e, N.Not):
            v = self.eval(e.expr, env, row)
            _need(v, e)
            return not v
        if isinstance(e, N.Call):
            return self._call(e, [self.eval(a, env, row) for a in e.args])
        if isinstance(e, N.BinOp):
            return self._binop(e, env, row)
        raise RuntimeFault(f"cannot evaluate {type(e).__name__}")

    def cell(self, r: RowRef, col: str) -> Any:
        if not self.ws.has_row(r.sheet, r.row_id):
            raise RuntimeFault(f"row {r.row_id} no longer exists in {r.sheet}")
        return self.ws.read(r.sheet, r.row_id, col)

    def _call(self, e: N.Call, a: list[Any]) -> Any:
        f = e.func
        if f == "is_empty":
            return a[0] is EMPTY
        for v in a:
            _need(v, e)
        if f == "today":
            return self.ws.now.date()
        if f == "now":
            return self.ws.now
        if f == "date_of":
            return a[0].date()
        if f == "time_of":
            return a[0].strftime("%H:%M")
        if f == "days_between":
            d1, d2 = (x.date() if isinstance(x, datetime) else x for x in a)
            return Decimal((d2 - d1).days)
        if f in ("min", "max"):
            return min(a) if f == "min" else max(a)
        if f == "round":
            return a[0].quantize(Decimal(1), ROUND_HALF_UP)
        if f == "lower":
            return str(a[0]).lower()
        if f == "contains":
            return str(a[1]).lower() in str(a[0]).lower()
        raise RuntimeFault(f"unknown function {f}")

    def _binop(self, e: N.BinOp, env: dict, row: RowRef | None) -> Any:
        if e.op in ("and", "or"):
            left = self.eval(e.left, env, row)
            _need(left, e)
            if (e.op == "and") != bool(left):
                return bool(left)
            right = self.eval(e.right, env, row)
            _need(right, e)
            return bool(right)
        a, b = self.eval(e.left, env, row), self.eval(e.right, env, row)
        _need(a, e)
        _need(b, e)
        op = e.op
        if op in ("==", "!=", "<", "<=", ">", ">="):
            a, b = _cmpable(a), _cmpable(b)
            return {"==": a == b, "!=": a != b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
        return _arith(op, a, b, e)


def _cmpable(v: Any) -> Any:
    return v.amount if isinstance(v, Money) else v


def _arith(op: str, a: Any, b: Any, e: N.BinOp) -> Any:
    try:
        if isinstance(a, Money) and isinstance(b, Money) and op in "+-":
            return Money(a.amount + b.amount if op == "+" else a.amount - b.amount)
        if isinstance(a, Money) and isinstance(b, Decimal) and op in "*/":
            return Money(a.amount * b if op == "*" else a.amount / b)
        if isinstance(a, Decimal) and isinstance(b, Money) and op == "*":
            return Money(a * b.amount)
        if isinstance(a, (date, datetime)) and isinstance(b, timedelta) and op in "+-":
            return a + b if op == "+" else a - b
        if isinstance(a, timedelta) and isinstance(b, (date, datetime, timedelta)) and op == "+":
            return a + b
        if isinstance(a, Decimal) and isinstance(b, Decimal):
            return {"+": a + b, "-": a - b, "*": a * b, "/": a / b}[op]
        if isinstance(a, str) and isinstance(b, str) and op == "+":
            return a + b
    except (ArithmeticError, ZeroDivisionError) as exc:
        raise RuntimeFault(f"line {e.line}: {exc}") from exc
    raise RuntimeFault(f"line {e.line}: bad operation {type(a).__name__} {op} {type(b).__name__}")


def _need(v: Any, e) -> None:
    if v is EMPTY:
        raise EmptyValueFault(f"line {getattr(e, 'line', 0)}: empty value used in a calculation or comparison")


def _show(e) -> str:
    if isinstance(e, N.Attr):
        return f"{e.obj}.{e.attr}"
    if isinstance(e, N.Name):
        return e.name
    if isinstance(e, N.Call):
        return f"{e.func}(...)"
    return type(e).__name__
