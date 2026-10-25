"""The Aether interpreter: runs a checked procedure against a mock workspace.

    Interpreter(proc, policy, workspace, provider).run(row_id=..., params=...) -> RunResult

Fail closed: a failed run-time guard performs nothing, logs `blocked`, and ends
the run (X106 instead takes the approval's `else` path, as SPEC.md section 3 says).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from checker import nodes as N
from checker.check import check
from checker.diagnostics import errors
from checker.policy import build_model

from . import batch as B
from .approvals import ApprovalRequest, Item, Provider, h
from .evaluator import EmptyValueFault, Evaluator, RuntimeFault, duration
from .values import (EMPTY, ApprovedBatchValue, ApprovedValue, DraftBatchValue, DraftValue,
                     Money, RowRef, fmt)
from .workspace import Workspace

MAX_EDIT_ROUNDS = 10


class _Stop(Exception):
    def __init__(self, reason: str, status: str = "stopped"):
        super().__init__(reason)
        self.reason, self.status = reason, status


class _Skip(Exception):
    pass


class _Blocked(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code} {detail}")
        self.code, self.detail = code, detail


@dataclass
class RunResult:
    status: str  # ok | stopped | blocked | error | refused
    reason: str
    audit: list[dict] = field(default_factory=list)


class Interpreter:
    def __init__(self, proc: N.Procedure, policy: N.Policy, ws: Workspace, provider: Provider,
                 run_id: str = "r-0001", max_steps: int = 10_000):
        self.proc, self.policy_ast, self.ws, self.provider = proc, policy, ws, provider
        self.pol = build_model(policy)
        self.run_id, self.max_steps = run_id, max_steps
        self.audit: list[dict] = []
        self.steps = 0
        self.n_approvals = 0
        cols = {alias: set(s.columns) for alias, s in proc.sheets.items()}
        self.ev = Evaluator(ws, cols)

    # ----- audit
    def log(self, op: str, result: str = "ok", **detail) -> None:
        self.audit.append({"run_id": self.run_id, "ts": self.ws.now.isoformat(), "step": self.steps,
                           "procedure": self.proc.name, "op": op, "detail": detail, "result": result})

    # ----- entry
    def run(self, row_id: str | None = None, params: dict | None = None) -> RunResult:
        problem = self._preflight()
        if problem:
            self.log("refused", "refused", reason=problem)
            return RunResult("refused", problem, self.audit)
        env: dict[str, Any] = {}
        t = self.proc.trigger
        if isinstance(t, N.NewRow):
            if row_id is None or not self.ws.has_row(t.sheet, row_id):
                return RunResult("refused", "trigger row missing", self.audit)
            env[t.var] = RowRef(t.sheet, row_id)
        elif isinstance(t, N.Requested):
            for name, typ in t.params:
                env[name] = _param(typ, (params or {}).get(name, EMPTY))
        self.log("start", trigger=type(t).__name__, policy_hash=h(self.policy_ast))
        try:
            self._block(self.proc.body, env, loop=False)
        except _Stop as s:
            self.log("stop", s.status, reason=s.reason)
            return RunResult(s.status, s.reason, self.audit)
        except _Blocked as b:
            self.log("blocked", "blocked", code=b.code, reason=b.detail)
            return RunResult("blocked", f"{b.code} {b.detail}", self.audit)
        except RuntimeFault as f:
            self.log("error", "error", reason=str(f))
            return RunResult("error", str(f), self.audit)
        self.log("end")
        return RunResult("ok", "", self.audit)

    def _preflight(self) -> str:
        bad = errors(check(self.proc, self.policy_ast))
        if bad:
            return "checker errors: " + "; ".join(str(d) for d in bad)
        for alias, sheet in self.proc.sheets.items():
            real = self.ws.sheets.get(alias)
            if real is None or real.title != sheet.title:
                return f"sheet {alias} \"{sheet.title}\" is not bound to that sheet in this workspace"
        for alias, title in self.proc.calendars.items():
            real = self.ws.calendars.get(alias)
            if real is None or real.title != title:
                return f"calendar {alias} \"{title}\" is not bound in this workspace"
        return ""

    # ----- control flow
    def _block(self, stmts, env: dict, loop: bool) -> None:
        scope = dict(env)
        for s in stmts:
            self.steps += 1
            if self.steps > self.max_steps:
                raise _Stop("step limit reached", "error")
            getattr(self, f"_s_{type(s).__name__.lower()}")(s, scope)

    def _else(self, els: N.Else, env: dict) -> None:
        if isinstance(els, N.ElseSkip):
            raise _Skip()
        raise _Stop(self.ev.render(els.reason, env).text)

    # ----- statements
    def _s_let(self, s: N.Let, env: dict) -> None:
        env[s.name] = self._rhs(s.rhs, env)

    def _s_if(self, s: N.If, env: dict) -> None:
        if self.ev.eval(s.cond, env):
            self._block(s.then, env, loop=False)
        elif s.els is not None:
            self._block(s.els, env, loop=False)

    def _s_foreach(self, s: N.ForEach, env: dict) -> None:
        rows: list[RowRef] = env[s.table]
        if len(rows) > s.bound:
            self.log("loop_truncated", table=s.table, rows=len(rows), bound=s.bound)
        for r in rows[: s.bound]:
            try:
                self._block(s.body, {**env, s.var: r}, loop=True)
            except _Skip:
                continue

    def _s_stop(self, s: N.Stop, env: dict) -> None:
        raise _Stop(self.ev.render(s.reason, env).text)

    def _s_skip(self, s: N.Skip, env: dict) -> None:
        raise _Skip()

    def _s_log(self, s: N.Log, env: dict) -> None:
        self.log("log", text=self.ev.render(s.text, env).text)

    def _s_notify(self, s: N.Notify, env: dict) -> None:
        text = self.ev.render(s.text, env).text
        self.ws.notify_owner(text)
        self.log("notify_owner", text=text)

    def _s_wait(self, s: N.Wait, env: dict) -> None:
        self.ws.now += duration(s.duration)
        self.log("wait", until=self.ws.now.isoformat())

    def _s_update(self, s: N.Update, env: dict) -> None:
        r: RowRef = env[s.row]
        if not self.ws.has_row(r.sheet, r.row_id):
            raise RuntimeFault(f"row {r.row_id} no longer exists")
        for col, e in s.assigns:
            v = self.ev.eval(e, env)
            self.ws.write(r.sheet, r.row_id, col, v)
        self.log("update", sheet=r.sheet, row=r.row_id, cols=[c for c, _ in s.assigns])

    def _s_append(self, s: N.Append, env: dict) -> None:
        values = {col: self.ev.eval(e, env) for col, e in s.fields}
        rid = self.ws.append(s.sheet, values)
        self.log("append", sheet=s.sheet, row=rid)

    def _s_cancel(self, s: N.Cancel, env: dict) -> None:
        eid = fmt(self.ev.eval(s.event_id, env))
        found = self.ws.cancel(s.calendar, eid)
        self.log("cancel", calendar=s.calendar, event=eid, found=found)

    def _s_send(self, s: N.Send, env: dict) -> None:
        v = env[s.name]
        if isinstance(v, ApprovedValue):
            self._send_single(v)
        elif isinstance(v, ApprovedBatchValue):
            self._send_batch(v)
        else:  # the checker rules this out; fail closed anyway
            raise _Blocked("X102", "send of an unapproved value")

    def _s_refund(self, s: N.Refund, env: dict) -> None:
        self._money("refund", s.amount, fmt(self.ev.eval(s.ident, env)), s.reason, s.ask, env)

    def _s_order(self, s: N.Order, env: dict) -> None:
        what = self.ev.render(s.what, env).text
        supplier = fmt(self.ev.eval(s.supplier, env))
        self._money("order", s.cost, f"{what} from {supplier}", None, s.ask, env)

    # ----- right-hand sides
    def _rhs(self, r, env: dict) -> Any:
        if isinstance(r, N.Fetch):
            return [RowRef(r.sheet, rid) for rid in self.ws.row_ids(r.sheet)]
        if isinstance(r, N.Filter):
            return [row for row in env[r.table] if self._matches(r.cond, env, row)]
        if isinstance(r, N.Find):
            for row in env[r.table]:
                if self._matches(r.cond, env, row):
                    return row
            self.log("find_none", table=r.table)
            self._else(r.els, env)
        if isinstance(r, N.Sort):
            rows = list(env[r.table])
            filled = [x for x in rows if self.ev.cell(x, r.col) is not EMPTY]
            blank = [x for x in rows if x not in filled]
            filled.sort(key=lambda x: _sortkey(self.ev.cell(x, r.col)), reverse=r.desc)
            out = filled + blank  # blank cells always sort last
            return out[: r.first] if r.first is not None else out
        if isinstance(r, N.Summarize):
            return self._summarize(r, env)
        if isinstance(r, N.Draft):
            return B.render_message(self.ev, r.msg, env).draft
        if isinstance(r, N.DraftEach):
            return DraftBatchValue(r.var, list(env[r.table]), r.bound, r.msg, dict(env))
        if isinstance(r, N.Approve):
            return self._approve_batch(r, env) if r.batch else self._approve_single(r, env)
        if isinstance(r, N.Book):
            f = {k: self.ev.eval(e, env) for k, e in r.fields}
            eid = self.ws.book(r.calendar, fmt(f["title"]), f["at"], f.get("length"))
            self.log("book", calendar=r.calendar, event=eid)
            return eid
        return self.ev.eval(r, env)

    def _matches(self, cond: N.Expr, env: dict, row: RowRef) -> bool:
        """A row whose condition hits a blank cell is left out (and logged), not fatal."""
        try:
            return bool(self.ev.eval(cond, env, row))
        except EmptyValueFault as exc:
            self.log("row_excluded", sheet=row.sheet, row=row.row_id, reason=str(exc))
            return False

    def _summarize(self, r: N.Summarize, env: dict) -> Any:
        rows = env[r.table]
        if r.agg == "count":
            return Decimal(len(rows))
        vals = [v for v in (self.ev.cell(x, r.col) for x in rows) if v is not EMPTY]
        if not vals:
            return EMPTY
        if r.agg in ("min", "max"):
            return min(vals) if r.agg == "min" else max(vals)
        if isinstance(vals[0], Money):
            total = Money(sum((v.amount for v in vals), Decimal(0)))
            return total if r.agg == "sum" else Money(total.amount / len(vals))
        total = sum(vals, Decimal(0))
        return total if r.agg == "sum" else total / len(vals)

    # ----- approvals
    def _ask(self, req: ApprovalRequest):
        d = self.provider.decide(req)
        self.ws.now += d.delay
        if d.action == "timeout" or d.delay > req.timeout:
            return "timeout", d
        return d.action, d

    def _new_id(self) -> str:
        self.n_approvals += 1
        return f"{self.run_id}-a{self.n_approvals}"

    def _approve_single(self, r: N.Approve, env: dict) -> ApprovedValue:
        d: DraftValue = env[r.draft]
        timeout = duration(r.timeout)
        for _ in range(MAX_EDIT_ROUNDS):
            if d.incomplete:
                self.log("blocked", "blocked", code="X106", missing=d.incomplete)
                self._else(r.els, env)
            rid = self._new_id()
            item = Item(str(d.to), d.text())
            action, dec = self._ask(ApprovalRequest(rid, "message", [item], [item], timeout))
            self.log("approval", action, id=rid, text_hash=h(item.text), to=item.to)
            if action == "approve":
                if dec.after:
                    dec.after()
                return ApprovedValue(d, rid)
            if action == "edit":
                d = self._edit_single(d, dec.new_text or "", env)
                continue
            self._else(r.els, env)
        self.log("approval", "deny", reason="too many edit rounds")
        self._else(r.els, env)

    def _edit_single(self, d: DraftValue, text: str, env: dict) -> DraftValue:
        rows = {k for k, v in env.items() if isinstance(v, RowRef)}
        parsed, err = B.check_edit(text, env, self.pol, rows)
        if parsed is None:
            self.log("edit_rejected", "rejected", reason=err)
            return d
        rendered = self.ev.render(parsed, env)
        self.log("edit", old_hash=h(d.body), new_hash=h(rendered.text))
        return DraftValue(d.channel, d.to, d.subject, rendered.text, list(rendered.missing))

    def _approve_batch(self, r: N.Approve, env: dict) -> ApprovedBatchValue:
        b: DraftBatchValue = env[r.draft]
        timeout = duration(r.timeout)
        for _ in range(MAX_EDIT_ROUNDS):
            msgs = B.render_batch(self.ev, b.msg, b.var, b.rows, b.scope)
            bad = [m for m in msgs if m.draft.incomplete]
            if bad:
                self.log("blocked", "blocked", code="X106", messages=len(bad))
                self._else(r.els, env)
            limit = min(b.bound, self.pol.batch_max or b.bound)
            if len(msgs) > limit:
                raise _Blocked("X104", f"batch of {len(msgs)} above max {limit}")
            rid = self._new_id()
            all_items = B.items(msgs)
            picks = B.select_preview(msgs, self.pol.batch_preview or len(msgs))
            req = ApprovalRequest(rid, "batch", all_items, [all_items[i] for i in picks], timeout, b.msg.body.raw)
            action, dec = self._ask(req)
            hashes = (B.template_hash(b.msg), B.recipients_hash(msgs), B.messages_hash(msgs))
            self.log("approval", action, id=rid, count=len(msgs), preview=len(picks), hashes=list(hashes))
            if action == "approve":
                expires = self.ws.now + (self.pol.batch_valid or timedelta(0))
                approved = ApprovedBatchValue(b, rid, *hashes, len(msgs), expires)
                if dec.after:
                    dec.after()
                return approved
            if action == "edit":
                parsed, err = B.check_edit(dec.new_text or "", {**b.scope, b.var: b.rows[0]} if b.rows else b.scope,
                                           self.pol, {b.var})
                if parsed is None:
                    self.log("edit_rejected", "rejected", reason=err)
                else:
                    self.log("edit", old_hash=h(b.msg.body.raw), new_hash=h(parsed.raw))
                    b = replace(b, msg=replace(b.msg, body=parsed))
                continue
            self._else(r.els, env)
        self.log("approval", "deny", reason="too many edit rounds")
        self._else(r.els, env)

    # ----- sending
    def _period_start(self, period: str) -> datetime:
        day = self.ws.now.replace(hour=0, minute=0, second=0, microsecond=0)
        return day - timedelta(days=day.weekday()) if period == "week" else day

    def _send_guards(self, count: int) -> None:
        if self.pol.window:
            start, end = self.pol.window
            hm = self.ws.now.strftime("%H:%M")
            if not (start <= hm < end):
                raise _Blocked("X105", f"{hm} outside {start}-{end}")
        for period, cap in self.pol.sends.items():
            if period not in ("day", "week"):
                continue
            begin = self._period_start(period)
            span = timedelta(days=7 if period == "week" else 1)
            used = self.ws.sends_in(begin, begin + span)
            if used + count > cap:
                raise _Blocked("X104", f"send cap {cap} per {period} ({used} used, {count} more)")

    def _send_single(self, a: ApprovedValue) -> None:
        if a.used:
            raise _Blocked("X103", f"approval {a.approval_id} already used")
        self._send_guards(1)
        a.used = True
        d = a.draft
        self.ws.deliver(d.channel, str(d.to), d.subject, d.body)
        self.log("send", to=str(d.to), approval=a.approval_id, text_hash=h(d.text()))

    def _send_batch(self, a: ApprovedBatchValue) -> None:
        if a.used:
            raise _Blocked("X103", f"approval {a.approval_id} already used")
        if self.ws.now > a.expires_at:
            raise _Blocked("X101", f"approval expired at {a.expires_at.isoformat()}")
        b = a.batch
        try:
            msgs = B.render_batch(self.ev, b.msg, b.var, b.rows, b.scope)
        except RuntimeFault as exc:
            raise _Blocked("X102", f"data changed: {exc}") from exc
        now = (B.template_hash(b.msg), B.recipients_hash(msgs), B.messages_hash(msgs))
        if now != (a.template_hash, a.recipients_hash, a.messages_hash) or len(msgs) != a.count:
            raise _Blocked("X102", "template, recipients, or message data changed since approval")
        self._send_guards(len(msgs))
        a.used = True
        for m in msgs:
            self.ws.deliver(m.draft.channel, str(m.draft.to), m.draft.subject, m.draft.body)
        self.log("send_batch", approval=a.approval_id, count=len(msgs), messages_hash=a.messages_hash)

    # ----- money
    def _money(self, op: str, amount_e: N.Expr, ident: str, reason: N.Str | None, ask: N.Ask | None, env: dict) -> None:
        amount = self.ev.eval(amount_e, env)
        if not isinstance(amount, Money) or amount.amount <= 0:
            raise _Blocked("X104", f"{op} amount {amount} must be more than $0")
        cap = self.pol.money_cap(op, "action")
        if cap is None or amount.amount > cap:
            raise _Blocked("X104", f"{op} {amount} above per-action cap")
        day_cap = self.pol.money_cap(op, "day")
        begin = self._period_start("day")
        spent = self.ws.money_in(op, begin, begin + timedelta(days=1))
        if day_cap is None or spent + amount.amount > day_cap:
            raise _Blocked("X104", f"{op} daily cap ${day_cap} ({spent} already)")
        why = self.ev.render(reason, env).text if reason is not None else ""
        text = f"{op.capitalize()} {amount} for {ident}" + (f": {why}" if why else "")
        if ask is not None:
            rid = self._new_id()
            item = Item(ident, text)
            action, _ = self._ask(ApprovalRequest(rid, "money", [item], [item], duration(ask.timeout)))
            self.log("approval", action, id=rid, text_hash=h(text))
            if action != "approve":  # edits are not offered for money actions
                self._else(ask.els, env)
        elif self.pol.auto_refund is None or op != "refund" or amount.amount > self.pol.auto_refund:
            raise _Blocked("X104", f"{op} {amount} needs approval")
        self.ws.move_money(op, amount, ident, text)
        self.log(op, amount=str(amount), ident=ident, approved=ask is not None)


def _param(typ: str, v: Any) -> Any:
    """Convert an on-request input (often text from a form) to its declared type."""
    if v is EMPTY or v is None:
        return EMPTY
    if isinstance(v, (Money, bool, date, datetime)) and not isinstance(v, str):
        return v
    s = str(v).strip()
    try:
        if typ == "Number":
            return Decimal(s)
        if typ == "Money":
            return Money(Decimal(s.lstrip("$")))
        if typ == "Date":
            return date.fromisoformat(s)
        if typ == "DateTime":
            return datetime.fromisoformat(s)
        if typ == "Bool":
            return s.lower() in ("true", "yes", "1")
    except (ArithmeticError, ValueError) as exc:
        raise RuntimeFault(f"input {s!r} is not a valid {typ}") from exc
    return s


def _sortkey(v: Any) -> Any:
    return v.amount if isinstance(v, Money) else v
