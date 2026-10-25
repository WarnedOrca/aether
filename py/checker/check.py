"""Static checker: types + policy rules (SPEC.md sections 3-5, codes in section 7).

    check(procedure, policy) -> list[Diagnostic]

An empty error list means the checker could prove every rule it is responsible
for. It does not mean the program does what the owner meant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from . import nodes as N
from .diagnostics import Diagnostic
from .exprs import ExprTyper, Info, Scope, facts_when, row_sheet
from .policy import MAX_WAIT, PolicyModel, Usage, build_model, to_timedelta, validate


@dataclass
class _Ctx:
    loop_depth: int = 0
    multiplier: int = 1


@dataclass
class _State:
    diags: list[Diagnostic] = field(default_factory=list)
    usage: dict[str, bool] = field(default_factory=lambda: {"refund": False, "order": False, "send": False, "batch": False})
    worst: dict[str, Decimal] = field(default_factory=lambda: {"refund": Decimal(0), "order": Decimal(0)})


def _exits(stmts: tuple[N.Stmt, ...] | None) -> bool:
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, (N.Stop, N.Skip)):
        return True
    if isinstance(last, N.If):
        return _exits(last.then) and _exits(last.els)
    return False


class Checker:
    def __init__(self, proc: N.Procedure, policy: N.Policy):
        self.proc = proc
        self.pol: PolicyModel = build_model(policy)
        self.st = _State()
        self.typer = ExprTyper(self._report, self._on_read, proc.sheets)

    # ----- reporting
    def _report(self, code: str, detail: str, line: int = 0) -> None:
        self.st.diags.append(Diagnostic(code, detail, line))

    def _on_read(self, sheet: str, col: str, line: int) -> None:
        if col not in self.pol.reads.get(sheet, set()):
            self._report("E401", f"reads {sheet}.{col}", line)

    # ----- entry
    def run(self) -> list[Diagnostic]:
        scope = Scope()
        self._trigger(scope)
        self._block(self.proc.body, scope, _Ctx())
        for op in ("refund", "order"):
            day = self.pol.money_cap(op, "day")
            if self.st.usage[op] and day is not None and self.st.worst[op] > day:
                self._report("E202", f"worst-case {op} total ${self.st.worst[op]} per run above daily cap ${day}")
        usage = Usage(**self.st.usage)
        return validate(self.pol, usage) + self.st.diags

    def _trigger(self, scope: Scope) -> None:
        t = self.proc.trigger
        if isinstance(t, N.NewRow):
            if t.sheet not in self.proc.sheets:
                self._report("E601", f"unknown sheet {t.sheet}")
            elif t.sheet not in self.pol.reads:
                self._report("E401", f"trigger reads sheet {t.sheet}")
            scope.vars[t.var] = Info(f"Row:{t.sheet}")
        elif isinstance(t, N.Requested):
            for name, typ in t.params:
                scope.vars[name] = Info(typ, from_column=False)

    # ----- helpers
    def _define(self, scope: Scope, name: str, info: Info, line: int) -> None:
        if scope.lookup(name) is not None:
            self._report("E601", f"'{name}' is already defined (names are bound once)", line)
        scope.vars[name] = info

    def _table(self, name: str, scope: Scope, line: int) -> str | None:
        info = scope.lookup(name)
        if info is None or not info.type.startswith("Table:"):
            self._report("E601", f"'{name}' is not a table", line)
            return None
        return row_sheet(info.type)

    def _else(self, els: N.Else, ctx: _Ctx) -> None:
        if isinstance(els, N.ElseSkip) and ctx.loop_depth == 0:
            self._report("E502", "'else skip' outside a loop", els.line)

    def _message_text(self, s: N.Str, scope: Scope, extra: Scope | None = None) -> None:
        sc = extra or scope
        for p in s.parts:
            if not isinstance(p, N.Interp):
                continue
            info = self.typer.type_of(p.expr, sc)
            leaked = info.sources & self.pol.deny_reveal
            for sheet, col in sorted(leaked):
                self._report("E301", f"{sheet}.{col} appears in a message", s.line)
            if info.from_column and p.default is None:
                self._report("W101", f"{{{_show(p.expr)}}} has no default", s.line)

    def _message(self, msg: N.Message, scope: Scope, line: int) -> None:
        to = self.typer.type_of(msg.to, scope)
        need = "Phone" if msg.channel == "sms" else "Email"
        if to.type not in (need, "?"):
            self._report("E601", f"{msg.channel} needs a {need} recipient, got {to.type}", line)
        if not to.contact or not to.contact <= self.pol.contacts:
            self._report("E302", f"recipient {_show(msg.to)}", line)
        if msg.subject is not None:
            self._message_text(msg.subject, scope)
        self._message_text(msg.body, scope)

    def _check_amount(self, op: str, amount: N.Expr, scope: Scope, line: int, ctx: _Ctx) -> Info:
        info = self.typer.type_of(amount, scope)
        if info.type not in ("Money", "?"):
            self._report("E601", f"{op} amount must be Money, got {info.type}", line)
        cap = self.pol.money_cap(op, "action")
        if cap is not None:
            if info.bound is None or info.bound > cap:
                self._report("E201", f"{op} amount {_show(amount)} not proven <= ${cap}", line)
            self.st.worst[op] += cap * ctx.multiplier
        return info

    # ----- statements
    def _block(self, stmts: tuple[N.Stmt, ...], scope: Scope, ctx: _Ctx) -> None:
        for s in stmts:
            self._stmt(s, scope, ctx)

    def _stmt(self, s: N.Stmt, scope: Scope, ctx: _Ctx) -> None:
        method = getattr(self, f"_s_{type(s).__name__.lower()}")
        method(s, scope, ctx)

    def _s_let(self, s: N.Let, scope: Scope, ctx: _Ctx) -> None:
        self._define(scope, s.name, self._rhs(s.rhs, scope, ctx, s.line), s.line)

    def _s_append(self, s: N.Append, scope: Scope, ctx: _Ctx) -> None:
        if s.sheet not in self.pol.appends:
            self._report("E401", f"append to {s.sheet}", s.line)
        self._fields(s.sheet, s.fields, scope, s.line)

    def _s_update(self, s: N.Update, scope: Scope, ctx: _Ctx) -> None:
        info = scope.lookup(s.row)
        if info is None or not info.type.startswith("Row:"):
            self._report("E601", f"'{s.row}' is not a row", s.line)
            return
        sheet = row_sheet(info.type)
        for col, _ in s.assigns:
            if col not in self.pol.writes.get(sheet, set()):
                self._report("E401", f"writes {sheet}.{col}", s.line)
        self._fields(sheet, s.assigns, scope, s.line)

    def _fields(self, sheet: str, fields, scope: Scope, line: int) -> None:
        cols = self.proc.sheets[sheet].columns if sheet in self.proc.sheets else {}
        if sheet not in self.proc.sheets:
            self._report("E601", f"unknown sheet {sheet}", line)
        for col, expr in fields:
            info = self.typer.type_of(expr, scope)
            want = cols.get(col)
            if want is None:
                self._report("E601", f"unknown column {sheet}.{col}", line)
            elif info.type not in (want.type, "?") and not (want.type in ("Text",) and info.type in ("Phone", "Email")):
                self._report("E601", f"{sheet}.{col} is {want.type}, got {info.type}", line)

    def _s_send(self, s: N.Send, scope: Scope, ctx: _Ctx) -> None:
        self.st.usage["send"] = True
        info = scope.lookup(s.name)
        if info is None:
            self._report("E601", f"unknown name '{s.name}'", s.line)
        elif info.type in ("Draft", "DraftBatch"):
            self._report("E101", f"'{s.name}' is a {info.type}", s.line)
        elif info.type not in ("Approved", "ApprovedBatch"):
            self._report("E601", f"cannot send a {info.type}", s.line)

    def _s_notify(self, s: N.Notify, scope: Scope, ctx: _Ctx) -> None:
        self.typer.type_of(s.text, scope)

    def _s_log(self, s: N.Log, scope: Scope, ctx: _Ctx) -> None:
        self.typer.type_of(s.text, scope)

    def _s_cancel(self, s: N.Cancel, scope: Scope, ctx: _Ctx) -> None:
        self._calendar(s.calendar, s.line)
        info = self.typer.type_of(s.event_id, scope)
        if info.type not in ("Text", "?"):
            self._report("E601", "event id must be Text", s.line)

    def _calendar(self, cal: str, line: int) -> None:
        if cal not in self.proc.calendars:
            self._report("E601", f"unknown calendar {cal}", line)
        if cal not in self.pol.calendars:
            self._report("E402", f"calendar {cal}", line)

    def _s_wait(self, s: N.Wait, scope: Scope, ctx: _Ctx) -> None:
        if to_timedelta(s.duration) > MAX_WAIT:
            self._report("E501", "wait longer than 30 days", s.line)

    def _s_refund(self, s: N.Refund, scope: Scope, ctx: _Ctx) -> None:
        self.st.usage["refund"] = True
        info = self._check_amount("refund", s.amount, scope, s.line, ctx)
        self.typer.type_of(s.ident, scope)
        if s.ask is not None:
            self._else(s.ask.els, ctx)
            return
        auto = self.pol.auto_refund
        if auto is None or info.bound is None or info.bound > auto:
            self._report("E102", "refund without approval not proven within the auto-refund threshold", s.line)

    def _s_order(self, s: N.Order, scope: Scope, ctx: _Ctx) -> None:
        self.st.usage["order"] = True
        self._check_amount("order", s.cost, scope, s.line, ctx)
        self.typer.type_of(s.what, scope)
        sup = s.supplier
        if isinstance(sup, N.Str) and not any(isinstance(p, N.Interp) for p in sup.parts):
            ok = sup.raw in self.pol.supplier_lits
        else:
            info = self.typer.type_of(sup, scope)
            ok = bool(info.contact) and info.contact <= self.pol.supplier_cols
        if not ok:
            self._report("E303", f"supplier {_show(sup)}", s.line)
        if s.ask is None:
            self._report("E102", "order without 'ask owner first'", s.line)
        else:
            self._else(s.ask.els, ctx)

    def _s_if(self, s: N.If, scope: Scope, ctx: _Ctx) -> None:
        cond = self.typer.type_of(s.cond, scope)
        if cond.type not in ("Bool", "?"):
            self._report("E601", "if condition must be Bool", s.line)
        then_scope = scope.child()
        then_scope.facts.update(facts_when(s.cond, True))
        self._block(s.then, then_scope, ctx)
        if s.els is not None:
            else_scope = scope.child()
            else_scope.facts.update(facts_when(s.cond, False))
            self._block(s.els, else_scope, ctx)
        # guard-and-exit: if one branch always leaves, the other branch's facts hold afterwards
        if _exits(s.then):
            for k, v in facts_when(s.cond, False).items():
                scope.facts[k] = min(v, scope.facts.get(k, v))
        if s.els is not None and _exits(s.els):
            for k, v in facts_when(s.cond, True).items():
                scope.facts[k] = min(v, scope.facts.get(k, v))

    def _s_foreach(self, s: N.ForEach, scope: Scope, ctx: _Ctx) -> None:
        sheet = self._table(s.table, scope, s.line)
        if s.bound is None:
            self._report("E501", f"loop over {s.table} needs 'up to N'", s.line)
        inner = scope.child()
        self._define(inner, s.var, Info(f"Row:{sheet}" if sheet else "?"), s.line)
        self._block(s.body, inner, _Ctx(ctx.loop_depth + 1, ctx.multiplier * (s.bound or 1)))

    def _s_stop(self, s: N.Stop, scope: Scope, ctx: _Ctx) -> None:
        self.typer.type_of(s.reason, scope)

    def _s_skip(self, s: N.Skip, scope: Scope, ctx: _Ctx) -> None:
        if ctx.loop_depth == 0:
            self._report("E502", "'skip' outside a loop", s.line)

    # ----- right-hand sides
    def _rhs(self, r: N.Rhs, scope: Scope, ctx: _Ctx, line: int) -> Info:
        if isinstance(r, N.Fetch):
            if r.sheet not in self.proc.sheets:
                self._report("E601", f"unknown sheet {r.sheet}", line)
                return Info("?")
            if r.sheet not in self.pol.reads:
                self._report("E401", f"fetch {r.sheet}", line)
            return Info(f"Table:{r.sheet}")
        if isinstance(r, (N.Filter, N.Find)):
            sheet = self._table(r.table, scope, line)
            if sheet is None:
                return Info("?")
            cond = self.typer.type_of(r.cond, scope, where_sheet=sheet)
            if cond.type not in ("Bool", "?"):
                self._report("E601", "where condition must be Bool", line)
            if isinstance(r, N.Find):
                self._else(r.els, ctx)
                return Info(f"Row:{sheet}")
            return Info(f"Table:{sheet}")
        if isinstance(r, N.Sort):
            sheet = self._table(r.table, scope, line)
            if sheet is not None:
                self.typer.column(sheet, r.col, line)
            return Info(f"Table:{sheet}" if sheet else "?")
        if isinstance(r, N.Summarize):
            return self._summarize(r, scope, line)
        if isinstance(r, N.Draft):
            self._message(r.msg, scope, line)
            return Info("Draft")
        if isinstance(r, N.DraftEach):
            return self._draft_each(r, scope, line)
        if isinstance(r, N.Approve):
            return self._approve(r, scope, ctx, line)
        if isinstance(r, N.Book):
            self._calendar(r.calendar, line)
            names = {k for k, _ in r.fields}
            if not {"title", "at"} <= names:
                self._report("E601", "book needs 'title' and 'at'", line)
            for k, e in r.fields:
                info = self.typer.type_of(e, scope)
                want = {"title": ("Text",), "at": ("Date", "DateTime"), "length": ("Duration",)}.get(k)
                if want is None:
                    self._report("E601", f"unknown book field '{k}'", line)
                elif info.type not in want + ("?",):
                    self._report("E601", f"book field '{k}' must be {'/'.join(want)}", line)
            return Info("Event")
        return self.typer.type_of(r, scope)

    def _summarize(self, r: N.Summarize, scope: Scope, line: int) -> Info:
        sheet = self._table(r.table, scope, line)
        if sheet is None:
            return Info("?")
        if r.agg == "count":
            if r.col is not None:
                self._report("E601", "count takes no column", line)
            return Info("Number")
        if r.col is None:
            self._report("E601", f"{r.agg} needs a column", line)
            return Info("?")
        col = self.typer.column(sheet, r.col, line)
        allowed = ("Number", "Money") + (("Date", "DateTime") if r.agg in ("min", "max") else ())
        if col.type not in allowed + ("?",):
            self._report("E601", f"cannot {r.agg} a {col.type} column", line)
        return Info(col.type, col.sources, from_column=True)

    def _draft_each(self, r: N.DraftEach, scope: Scope, line: int) -> Info:
        self.st.usage["batch"] = True
        if self.pol.mode != "batch":
            self._report("E104", "'draft each' needs 'approval batch'", line)
        if r.bound is None:
            self._report("E501", "'draft each' needs 'up to N'", line)
        elif self.pol.batch_max is not None and r.bound > self.pol.batch_max:
            self._report("E703", f"up to {r.bound} above batch max {self.pol.batch_max}", line)
        sheet = self._table(r.table, scope, line)
        inner = scope.child()
        inner.vars[r.var] = Info(f"Row:{sheet}" if sheet else "?")
        self._message(r.msg, inner, line)
        return Info("DraftBatch")

    def _approve(self, r: N.Approve, scope: Scope, ctx: _Ctx, line: int) -> Info:
        self._else(r.els, ctx)
        info = scope.lookup(r.draft)
        want = "DraftBatch" if r.batch else "Draft"
        if info is None or info.type != want:
            self._report("E601", f"'{r.draft}' is not a {want}", line)
        if r.batch:
            if self.pol.mode != "batch":
                self._report("E104", "batch approval needs 'approval batch'", line)
            return Info("ApprovedBatch")
        if self.pol.mode == "batch" and ctx.loop_depth > 0:
            self._report("E103", "use 'draft each' + batch approval instead", line)
        return Info("Approved")


def _show(e) -> str:
    if isinstance(e, N.Attr):
        return f"{e.obj}.{e.attr}"
    if isinstance(e, N.Name):
        return e.name
    if isinstance(e, N.Str):
        return f'"{e.raw}"'
    if isinstance(e, N.Call):
        return f"{e.func}(...)"
    return type(e).__name__


def check(proc: N.Procedure, policy: N.Policy) -> list[Diagnostic]:
    return Checker(proc, policy).run()
