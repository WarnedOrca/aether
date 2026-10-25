from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from checker.spec_examples import load_examples
from interpreter.approvals import Always, Decision, Script
from interpreter.sandbox import DEFAULT_NOW, run_monitored, workspace_for
from interpreter.values import EMPTY, Money

EX = load_examples()
TOMORROW = DEFAULT_NOW + timedelta(days=1, hours=1)


def _proc(name):
    p = EX.procedures[name]
    return p, EX.policies[p.policy]


def _appointments(n=3, **override):
    rows = [{"patient": f"P{i}", "phone": f"+1555000000{i}", "starts": TOMORROW, "status": "booked",
             "reason": "private reason"} for i in range(n)]
    for i, changes in override.items():
        rows[int(i[1:])].update(changes)
    return {"Appointments": rows}


def _deliveries(out):
    return [e for e in out.ws.connector_log if e["kind"] == "deliver"]


@pytest.mark.parametrize("name", sorted(EX.procedures))
@pytest.mark.parametrize("action", ["approve", "deny", "timeout"])
def test_every_example_runs_without_monitor_violations(name, action):
    proc, pol = _proc(name)
    ws = workspace_for(proc, rows=6)
    out = run_monitored(proc, pol, ws, Always(action), params={"days": 60})
    assert out.result.status in ("ok", "stopped", "blocked", "error"), out.result
    assert out.problems == []


def test_reminders_send_approved_texts_and_never_the_reason():
    proc, pol = _proc("AppointmentReminders")
    out = run_monitored(proc, pol, workspace_for(proc, data=_appointments()))
    assert out.result.status == "ok"
    sent = _deliveries(out)
    assert len(sent) == 3
    assert all("private reason" not in e["body"] for e in sent)
    assert sent[0]["body"].startswith("Hi P0, this is a reminder")
    rows = out.ws.sheets["Appointments"].rows.values()
    assert all(r["status"] == "reminded" for r in rows)


def test_denied_messages_are_not_sent():
    proc, pol = _proc("AppointmentReminders")
    out = run_monitored(proc, pol, workspace_for(proc, data=_appointments()), Always("deny"))
    assert _deliveries(out) == []
    assert out.problems == []


def test_default_used_for_blank_name():
    proc, pol = _proc("AppointmentReminders")
    out = run_monitored(proc, pol, workspace_for(proc, data=_appointments(1, r0={"patient": EMPTY})))
    assert _deliveries(out)[0]["body"].startswith("Hi there,")


def test_blank_cell_in_filter_excludes_only_that_row():
    proc, pol = _proc("AppointmentReminders")
    data = _appointments(3)
    data["Appointments"][1]["starts"] = EMPTY
    out = run_monitored(proc, pol, workspace_for(proc, data=data))
    assert out.result.status == "ok"
    assert len(_deliveries(out)) == 2
    assert any(a["op"] == "row_excluded" for a in out.result.audit)


def test_t6_blank_phone_blocks_only_that_message():
    proc, pol = _proc("AppointmentReminders")
    data = _appointments(3)
    data["Appointments"][1]["phone"] = EMPTY
    out = run_monitored(proc, pol, workspace_for(proc, data=data))
    assert out.result.status == "ok"
    assert len(_deliveries(out)) == 2
    assert any(a["detail"].get("code") == "X106" for a in out.result.audit)
    assert out.problems == []


def test_empty_in_arithmetic_stops_the_run():
    proc, pol = _proc("LowStockReorder")
    ws = workspace_for(proc, data={"Inventory": [{"item": "flour", "on_hand": Decimal(1), "minimum": Decimal(5),
                                                   "reorder_qty": EMPTY, "supplier": "Mill", "unit_cost": Money(Decimal(3))}]})
    out = run_monitored(proc, pol, ws)
    assert out.result.status == "error"


def test_t6_blank_interpolation_skips_to_next():
    proc, pol = _proc("NoShowFollowUp")
    rows = [{"patient": n, "phone": f"+1555000001{i}", "starts": DEFAULT_NOW, "status": "no-show",
             "reason": "x"} for i, n in enumerate(["A", EMPTY, "C"])]
    out = run_monitored(proc, pol, workspace_for(proc, data={"Appointments": rows}))
    assert out.result.status == "ok"
    assert [e["body"][:6] for e in _deliveries(out)] == ["Hi A, ", "Hi C, "]
    assert any(a["detail"].get("code") == "X106" for a in out.result.audit)


def test_batch_sends_all_after_one_approval():
    proc, pol = _proc("AppointmentRemindersBatch")
    out = run_monitored(proc, pol, workspace_for(proc, data=_appointments(4)))
    assert out.result.status == "ok"
    assert len(_deliveries(out)) == 4
    assert len(out.approvals.requests) == 1
    assert out.problems == []


def test_t1_data_change_after_batch_approval_blocks_everything():
    proc, pol = _proc("AppointmentRemindersBatch")
    ws = workspace_for(proc, data=_appointments(4))
    first = ws.row_ids("Appointments")[0]
    edit = Decision("approve", after=lambda: ws.write("Appointments", first, "patient", "Changed"))
    out = run_monitored(proc, pol, ws, Script([edit]))
    assert out.result.status == "blocked" and out.result.reason.startswith("X102")
    assert _deliveries(out) == []


def test_t2_expired_batch_approval_blocks():
    proc, pol = _proc("AppointmentRemindersBatch")
    ws = workspace_for(proc, data=_appointments(2))
    late = Decision("approve", after=lambda: setattr(ws, "now", ws.now + timedelta(hours=2)))
    out = run_monitored(proc, pol, ws, Script([late]))
    assert out.result.reason.startswith("X101")
    assert _deliveries(out) == []


def test_t3_reused_approval_blocks():
    from checker.mutate import mutate
    from checker.parser import parse_source
    src = mutate("ConfirmReservation", "  send ok\n", "  send ok\n  send ok\n")
    proc = parse_source(src).procedures["ConfirmReservation"]
    pol = EX.policies["RestaurantPolicy"]
    ws = workspace_for(proc, data={"Reservations": [
        {"guest": "G", "phone": "+15550001111", "party_size": Decimal(2), "at": TOMORROW, "status": "new"}]})
    out = run_monitored(proc, pol, ws)
    assert out.result.reason.startswith("X103")
    assert len(_deliveries(out)) == 1


def test_t4_non_positive_refund_blocks():
    proc, pol = _proc("ProcessReturn")
    ws = workspace_for(proc, data={"Returns": [{"order_id": "A1", "customer": "C", "phone": "+15550002222",
                                                 "amount": Money(Decimal("0")), "order_date": DEFAULT_NOW.date(),
                                                 "status": "new"}]})
    out = run_monitored(proc, pol, ws)
    assert out.result.reason.startswith("X104")
    assert not [e for e in ws.connector_log if e["kind"] == "money"]


def test_t5_send_outside_window_blocks():
    proc, pol = _proc("AppointmentReminders")
    ws = workspace_for(proc, data=_appointments(1), now=datetime(2026, 3, 2, 22, 0))
    ws.sheets["Appointments"].rows["r1"]["starts"] = ws.now + timedelta(days=1)
    out = run_monitored(proc, pol, ws)
    assert out.result.reason.startswith("X105")
    assert _deliveries(out) == []


def test_t7_blank_in_batch_blocks_whole_batch():
    proc, pol = _proc("AppointmentRemindersBatch")
    data = _appointments(3)
    data["Appointments"][2]["phone"] = EMPTY
    out = run_monitored(proc, pol, workspace_for(proc, data=data))
    assert out.result.status == "stopped"
    assert _deliveries(out) == []
    assert out.approvals.requests == []  # blocked before any preview


def test_t8_edit_adding_private_field_is_rejected():
    proc, pol = _proc("AppointmentReminders")
    script = Script([Decision("edit", new_text="Your visit is for {a.reason}"), Decision("approve")])
    out = run_monitored(proc, pol, workspace_for(proc, data=_appointments(1)), script)
    assert any(a["op"] == "edit_rejected" and "E301" in a["detail"]["reason"] for a in out.result.audit)
    assert "private reason" not in _deliveries(out)[0]["body"]


def test_edit_cancels_approval_and_reshows():
    proc, pol = _proc("AppointmentReminders")
    script = Script([Decision("edit", new_text="Hi {a.patient}, see you tomorrow."), Decision("approve")])
    out = run_monitored(proc, pol, workspace_for(proc, data=_appointments(1)), script)
    assert len(out.approvals.requests) == 2  # shown again after the edit
    assert _deliveries(out)[0]["body"] == "Hi P0, see you tomorrow."
    assert out.problems == []


def test_t9_batch_edit_gives_fresh_preview_and_new_hashes():
    proc, pol = _proc("AppointmentRemindersBatch")
    script = Script([Decision("edit", new_text="Hi {a.patient}, reminder for tomorrow."), Decision("approve")])
    out = run_monitored(proc, pol, workspace_for(proc, data=_appointments(3)), script)
    reqs = out.approvals.requests
    assert len(reqs) == 2 and reqs[0].items != reqs[1].items
    hashes = [a["detail"]["hashes"] for a in out.result.audit if a["op"] == "approval"]
    assert hashes[0] != hashes[1]
    assert all(e["body"].endswith("reminder for tomorrow.") for e in _deliveries(out))


def test_small_refund_is_automatic_larger_needs_approval():
    proc, pol = _proc("ProcessReturn")

    def ws_with(amount):
        return workspace_for(proc, data={"Returns": [{"order_id": "A1", "customer": "C", "phone": "+15550002222",
                                                       "amount": Money(Decimal(amount)), "order_date": DEFAULT_NOW.date(),
                                                       "status": "new"}]})
    small = run_monitored(proc, pol, ws_with("10.00"), Always("deny"))
    assert [e["op"] for e in small.ws.connector_log if e["kind"] == "money"] == ["refund"]
    big = run_monitored(proc, pol, ws_with("30.00"), Always("deny"))
    assert not [e for e in big.ws.connector_log if e["kind"] == "money"]
    assert small.problems == [] and big.problems == []


def test_wait_then_followup_reads_fresh_data():
    proc, pol = _proc("QuoteFollowUp")
    ws = workspace_for(proc, data={"Quotes": [{"id": "Q1", "customer": "K", "email": "k@example.com",
                                                "amount": Money(Decimal("400")), "status": "new"}]})
    out = run_monitored(proc, pol, ws)
    assert out.result.status == "ok"
    assert len(_deliveries(out)) == 2


def test_refused_when_sheet_not_bound():
    proc, pol = _proc("AppointmentReminders")
    ws = workspace_for(proc, data=_appointments(1))
    ws.sheets["Appointments"].title = "Payroll"
    out = run_monitored(proc, pol, ws)
    assert out.result.status == "refused"
