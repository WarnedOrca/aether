"""The monitor must not be vacuous: plant bugs in the interpreter and expect it to notice."""

import random
from datetime import timedelta

from interpreter import props
from interpreter.runtime import Interpreter
from interpreter.sandbox import run_monitored, workspace_for
from interpreter.approvals import Always


def _clinic():
    return props._example("AppointmentReminders")


def _rows(proc, n=3):
    now = workspace_for(proc).now
    return {"Appointments": [{"patient": f"P{i}", "phone": f"+1555200{i:04d}", "starts": now + timedelta(days=1),
                              "status": "booked", "reason": "secret-reason"} for i in range(n)]}


def test_catches_send_without_approval(monkeypatch):
    def bad_approve(self, r, env):  # pretend the owner approved without asking
        from interpreter.values import ApprovedValue
        return ApprovedValue(env[r.draft], "fake")
    monkeypatch.setattr(Interpreter, "_approve_single", bad_approve)
    proc, pol = _clinic()
    out = run_monitored(proc, pol, workspace_for(proc, data=_rows(proc)), Always("deny"))
    assert any(p.startswith("P1") for p in out.problems)


def test_catches_ignored_batch_binding(monkeypatch):
    original = Interpreter._send_batch

    def no_hash_check(self, a):
        a.messages_hash = a.recipients_hash = None  # forget what was approved
        b = a.batch
        from interpreter import batch as B
        msgs = B.render_batch(self.ev, b.msg, b.var, b.rows, b.scope)
        for m in msgs:
            self.ws.deliver(m.draft.channel, str(m.draft.to), m.draft.subject, m.draft.body)
        self.log("send_batch", approval=a.approval_id, count=len(msgs), messages_hash=None)
    monkeypatch.setattr(Interpreter, "_send_batch", no_hash_check)
    problems = props.batch_tamper_case(1, "name")
    assert any(p.startswith("P5") or p.startswith("P1") for p in problems)
    monkeypatch.setattr(Interpreter, "_send_batch", original)


def test_catches_send_cap_not_enforced(monkeypatch):
    monkeypatch.setattr(Interpreter, "_send_guards", lambda self, count: None)
    proc, pol = props._example("WinBack")  # GymPolicy: 200 sends per day
    rows = {"Members": [{"name": f"M{i}", "email": f"m{i}@example.com",
                         "ended": workspace_for(proc).now.date() - timedelta(days=5)} for i in range(150)]}
    ws = workspace_for(proc, data=rows)
    for _ in range(2):  # two runs on the same day: 300 sends > 200 cap
        out = run_monitored(proc, pol, ws, params={"days": 60})
    assert any(p.startswith("P3") for p in out.problems)


def test_catches_private_read_not_allowed(monkeypatch):
    original = Interpreter._s_log

    def leaky_log(self, s, env):
        row = next(v for v in env.values() if hasattr(v, "row_id"))
        self.ws.read("Appointments", row.row_id, "insurance_id")  # column not allowed by the policy
        original(self, s, env)
    monkeypatch.setattr(Interpreter, "_s_log", leaky_log)
    proc, pol = _clinic()
    out = run_monitored(proc, pol, workspace_for(proc, data=_rows(proc, 1)))
    assert any(p.startswith("P4") for p in out.problems)


def test_catches_money_over_cap(monkeypatch):
    monkeypatch.setattr(Interpreter, "_money", lambda self, op, amount_e, ident, reason, ask, env:
                        self.ws.move_money(op, __import__("interpreter.values", fromlist=["Money"]).Money(999), ident, "x")
                        or self.log(op, amount="999", ident=ident, approved=False))
    problems = []
    for seed in range(30):
        problems += props.run_case("ProcessReturn", seed, "approve", 0.0)
    assert any(p.startswith("P3") or p.startswith("P2") for p in problems)
