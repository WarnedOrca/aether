"""Expression typing, data-flow sources, and upper-bound facts for the checker.

Types are plain strings: Text Number Money Bool Date DateTime Duration Phone Email
Draft Approved DraftBatch ApprovedBatch Event, plus "Row:<sheet>" and "Table:<sheet>".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from . import nodes as N

TEXTLIKE = {"Text", "Phone", "Email"}
ORDERED = {"Number", "Money", "Date", "DateTime", "Text", "Duration"}


@dataclass(frozen=True)
class Info:
    """What the checker knows about a value."""

    type: str
    sources: frozenset = frozenset()  # (sheet, col) pairs this value was derived from
    contact: frozenset = frozenset()  # set only for a direct copy of one column value
    from_column: bool = False  # could be empty (came from a sheet cell)
    bound: Decimal | None = None  # proven upper bound, for Money/Number
    sheet: str | None = None  # for Row/Table/Draft: the sheet / recipient info


def row_sheet(t: str) -> str | None:
    return t.split(":", 1)[1] if t.startswith(("Row:", "Table:")) else None


@dataclass
class Scope:
    parent: "Scope | None" = None
    vars: dict[str, Info] = field(default_factory=dict)
    facts: dict[str, Decimal] = field(default_factory=dict)

    def lookup(self, name: str) -> Info | None:
        s: Scope | None = self
        while s is not None:
            if name in s.vars:
                return s.vars[name]
            s = s.parent
        return None

    def fact(self, key: str) -> Decimal | None:
        s: Scope | None = self
        best: Decimal | None = None
        while s is not None:
            if key in s.facts:
                best = s.facts[key] if best is None else min(best, s.facts[key])
            s = s.parent
        return best

    def child(self) -> "Scope":
        return Scope(parent=self)


def key(e: N.Expr) -> str | None:
    """Canonical text for expressions that facts can be attached to."""
    if isinstance(e, N.Name):
        return e.name
    if isinstance(e, N.Attr):
        return f"{e.obj}.{e.attr}"
    return None


# ----- facts from conditions (SPEC.md section 5: guards and guard-and-exit)

_FLIP = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "==", "!=": "!="}
_NEG = {"<": ">=", "<=": ">", ">": "<=", ">=": "<", "==": "!=", "!=": "=="}


def _lit(e: N.Expr) -> Decimal | None:
    if isinstance(e, (N.MoneyLit, N.Num)):
        return e.value
    return None


def facts_when(cond: N.Expr, truth: bool) -> dict[str, Decimal]:
    """Upper bounds that hold when `cond` evaluates to `truth`."""
    if isinstance(cond, N.Not):
        return facts_when(cond.expr, not truth)
    if isinstance(cond, N.BinOp) and cond.op in ("and", "or"):
        both = (cond.op == "and") == truth
        if not both:
            return {}
        out = dict(facts_when(cond.left, truth))
        for k, v in facts_when(cond.right, truth).items():
            out[k] = min(v, out.get(k, v))
        return out
    if isinstance(cond, N.BinOp) and cond.op in _NEG:
        op, left, right = cond.op, cond.left, cond.right
        if not truth:
            op = _NEG[op]
        if _lit(left) is not None and key(right) is not None:
            op, left, right = _FLIP[op], right, left
        k, v = key(left), _lit(right)
        if k is not None and v is not None and op in ("<", "<=", "=="):
            return {k: v}
    return {}


# ----- builtin functions: name -> (check(arg_types) -> result type or None)

def _builtin(name: str, args: list[str]) -> str | None:
    if name == "today" and not args:
        return "Date"
    if name == "now" and not args:
        return "DateTime"
    if name == "date_of" and args == ["DateTime"]:
        return "Date"
    if name == "time_of" and args == ["DateTime"]:
        return "Text"
    if name == "days_between" and len(args) == 2 and all(a in ("Date", "DateTime") for a in args):
        return "Number"
    if name in ("min", "max") and len(args) == 2 and args[0] == args[1] and args[0] in ("Number", "Money"):
        return args[0]
    if name == "round" and args == ["Number"]:
        return "Number"
    if name == "lower" and len(args) == 1 and args[0] in TEXTLIKE:
        return "Text"
    if name == "contains" and len(args) == 2 and all(a in TEXTLIKE for a in args):
        return "Bool"
    if name == "is_empty" and len(args) == 1:
        return "Bool"
    return None


def arith(op: str, a: str, b: str) -> str | None:
    if op in ("+", "-"):
        if a == b and a in ("Number", "Money", "Duration"):
            return a
        if a in ("Date", "DateTime") and b == "Duration":
            return a
        if op == "+" and a == "Duration" and b in ("Date", "DateTime"):
            return b
        if op == "+" and a in TEXTLIKE and b in TEXTLIKE:
            return "Text"
        return None
    if op == "*":
        pair = {a, b}
        if a == b == "Number":
            return "Number"
        if pair == {"Money", "Number"}:
            return "Money"
        return None
    if op == "/":
        if b == "Number" and a in ("Number", "Money"):
            return a
    return None


def comparable(op: str, a: str, b: str) -> bool:
    if a in TEXTLIKE and b in TEXTLIKE:
        return op in ("==", "!=") or (a == b == "Text")
    if a != b:
        return False
    return op in ("==", "!=") or a in ORDERED


Report = Callable[[str, str, int], None]


class ExprTyper:
    """Types expressions in a scope. `columns` is set inside `where` clauses."""

    def __init__(self, report: Report, on_read: Callable[[str, str, int], None], sheets: dict[str, N.Sheet]):
        self.report = report
        self.on_read = on_read
        self.sheets = sheets

    def column(self, sheet: str, col: str, line: int) -> Info:
        s = self.sheets.get(sheet)
        if s is None or col not in s.columns:
            self.report("E601", f"unknown column {sheet}.{col}", line)
            return Info("?")
        self.on_read(sheet, col, line)
        src = frozenset({(sheet, col)})
        return Info(s.columns[col].type, src, src, True)

    def type_of(self, e: N.Expr, scope: Scope, where_sheet: str | None = None) -> Info:
        t = self._type(e, scope, where_sheet)
        k = key(e)
        if k is not None and t.type in ("Money", "Number"):
            f = scope.fact(k)
            if f is not None:
                t = Info(t.type, t.sources, t.contact, t.from_column, f if t.bound is None else min(f, t.bound), t.sheet)
        return t

    def _type(self, e: N.Expr, scope: Scope, ws: str | None) -> Info:
        if isinstance(e, N.Num):
            return Info("Number", bound=e.value)
        if isinstance(e, N.MoneyLit):
            return Info("Money", bound=e.value)
        if isinstance(e, N.BoolLit):
            return Info("Bool")
        if isinstance(e, N.DurationLit):
            return Info("Duration")
        if isinstance(e, N.Str):
            srcs = frozenset()
            for p in e.parts:
                if isinstance(p, N.Interp):
                    srcs |= self.type_of(p.expr, scope, ws).sources
            return Info("Text", srcs)
        if isinstance(e, N.Name):
            is_col = ws is not None and e.name in self.sheets[ws].columns
            var = scope.lookup(e.name)
            if is_col and var is not None:
                self.report("E601", f"'{e.name}' is both a column and a variable", e.line)
            if is_col:
                return self.column(ws, e.name, e.line)
            if var is not None:
                return var
            self.report("E601", f"unknown name '{e.name}'", e.line)
            return Info("?")
        if isinstance(e, N.Attr):
            var = scope.lookup(e.obj)
            sheet = row_sheet(var.type) if var else None
            if var is None or not var.type.startswith("Row:"):
                self.report("E601", f"'{e.obj}' is not a row", e.line)
                return Info("?")
            return self.column(sheet, e.attr, e.line)
        if isinstance(e, N.Call):
            infos = [self.type_of(a, scope, ws) for a in e.args]
            res = _builtin(e.func, [i.type for i in infos])
            if res is None:
                self.report("E601", f"bad call {e.func}({', '.join(i.type for i in infos)})", e.line)
                return Info("?")
            srcs = frozenset().union(*[i.sources for i in infos]) if infos else frozenset()
            bound = None
            if e.func == "min":
                bounds = [i.bound for i in infos if i.bound is not None]
                bound = min(bounds) if bounds else None
            from_col = any(i.from_column for i in infos) and e.func != "is_empty"
            return Info(res, srcs, from_column=from_col, bound=bound)
        if isinstance(e, N.Not):
            i = self.type_of(e.expr, scope, ws)
            if i.type != "Bool":
                self.report("E601", "'not' needs a Bool", e.line)
            return Info("Bool", i.sources)
        if isinstance(e, N.BinOp):
            return self._binop(e, scope, ws)
        self.report("E601", f"unsupported expression {type(e).__name__}", getattr(e, "line", 0))
        return Info("?")

    def _binop(self, e: N.BinOp, scope: Scope, ws: str | None) -> Info:
        a, b = self.type_of(e.left, scope, ws), self.type_of(e.right, scope, ws)
        srcs = a.sources | b.sources
        fc = a.from_column or b.from_column
        if "?" in (a.type, b.type):
            return Info("?", srcs)
        if e.op in ("and", "or"):
            if a.type != "Bool" or b.type != "Bool":
                self.report("E601", f"'{e.op}' needs Bool values", e.line)
            return Info("Bool", srcs)
        if e.op in _NEG:
            if not comparable(e.op, a.type, b.type):
                self.report("E601", f"cannot compare {a.type} {e.op} {b.type}", e.line)
            return Info("Bool", srcs)
        res = arith(e.op, a.type, b.type)
        if res is None:
            self.report("E601", f"bad operation {a.type} {e.op} {b.type}", e.line)
            return Info("?", srcs)
        return Info(res, srcs, from_column=fc)
