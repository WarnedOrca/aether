import pytest

from checker.check import check
from checker.diagnostics import codes, errors
from checker.mutate import block_defining, check_text, mutate
from checker.spec_examples import load_examples

EX = load_examples()


@pytest.mark.parametrize("name", sorted(EX.procedures))
def test_spec_example_passes_checker(name):
    proc = EX.procedures[name]
    assert errors(check(proc, EX.policies[proc.policy])) == []


def _codes(src, proc, policy_text=None):
    return codes(errors(check_text(src, proc, policy_text)))


# ---------- SPEC.md section 11, R1-R14

def test_r1_send_without_approval():
    src = mutate("AppointmentReminders", "send ok", "send m")
    assert "E101" in _codes(src, "AppointmentReminders")


def test_r2_refund_over_cap():
    src = mutate("ProcessReturn", "refund r.amount for r.order_id reason \"return within 30 days\"\n",
                 "refund $80.00 for r.order_id reason \"return within 30 days\"\n")
    assert "E201" in _codes(src, "ProcessReturn")


def test_r3_private_column_in_message():
    src = mutate("AppointmentReminders", "Reply C to confirm.", "Reason: {a.reason}.")
    assert "E301" in _codes(src, "AppointmentReminders")


def test_r3b_private_column_through_let():
    src = mutate("AppointmentReminders", "    let m = draft",
                 "    let why = a.reason\n    let m = draft")
    src = src.replace("Reply C to confirm.", "About: {why}.")
    assert "E301" in _codes(src, "AppointmentReminders")


def test_r4_literal_recipient():
    src = mutate("AppointmentReminders", "draft sms to a.phone", 'draft sms to "555-0100"')
    assert "E302" in _codes(src, "AppointmentReminders")


def test_r5_fetch_unlisted_sheet():
    src = mutate("AppointmentReminders", "trigger every day at 09:00",
                 'sheet Payroll "Payroll" { name: Text, salary: Money }\n  trigger every day at 09:00')
    src = src.replace("let all = fetch Appointments", "let pay = fetch Payroll\n  let all = fetch Appointments")
    assert "E401" in _codes(src, "AppointmentReminders")


def test_r6_loop_without_bound():
    src = mutate("AppointmentReminders", "in tomorrows up to 100 {", "in tomorrows {")
    assert "E501" in _codes(src, "AppointmentReminders")


def test_r7_unlisted_supplier():
    src = mutate("LowStockReorder", "from i.supplier", 'from "Unlisted Co"')
    assert "E303" in _codes(src, "LowStockReorder")


def test_r8_worst_case_over_daily_cap():
    src = mutate("LowStockReorder", "in low up to 4 {", "in low up to 20 {")
    assert "E202" in _codes(src, "LowStockReorder")


def test_r9_single_approval_in_loop_under_batch_policy():
    src = mutate("AppointmentReminders", "policy ClinicPolicy\n", "policy ClinicBatchPolicy\n")
    assert "E103" in _codes(src, "AppointmentReminders")


def test_r10_batch_form_under_per_message_policy():
    src = mutate("AppointmentRemindersBatch", "policy ClinicBatchPolicy\n", "policy ClinicPolicy\n")
    assert "E104" in _codes(src, "AppointmentRemindersBatch")


def test_r11_missing_hard_cap():
    pol = mutate("ShopPolicy", "  limit refund $50 per action\n", "")
    assert "E701" in _codes(pol, "ProcessReturn")


def test_r12_threshold_above_cap():
    pol = mutate("ShopPolicy", "refund without approval up to $15", "refund without approval up to $5000")
    assert "E702" in _codes(pol, "ProcessReturn")


def test_r13_weakening_rule():
    pol = mutate("ClinicPolicy", "  limit sends 150 per day\n", "  allow send without approval\n  limit sends 150 per day\n")
    assert "E704" in _codes(pol, "AppointmentReminders")


def test_r14_batch_bound_above_max():
    src = mutate("AppointmentRemindersBatch", "in tomorrows up to 100 sms", "in tomorrows up to 500 sms")
    assert "E703" in _codes(src, "AppointmentRemindersBatch")


# ---------- other rules

def test_order_without_ask():
    src = mutate("LowStockReorder", ", ask owner first timeout 1 day else skip", "")
    assert "E102" in _codes(src, "LowStockReorder")


def test_auto_refund_needs_proof():
    # Removing the $15 guard: the auto refund is no longer proven within the threshold
    src = mutate("ProcessReturn", "if r.amount <= $15.00 {", "if r.amount <= $40.00 {")
    assert "E102" in _codes(src, "ProcessReturn")


def test_guard_and_exit_is_required_for_cap_proof():
    src = mutate("ProcessReturn", "  if r.amount > $50.00 {", "  if r.amount > $500.00 {")
    assert "E201" in _codes(src, "ProcessReturn")


def test_skip_outside_loop():
    src = mutate("ConfirmReservation", 'else stop "confirmation not approved"', "else skip")
    assert "E502" in _codes(src, "ConfirmReservation")


def test_write_not_allowed():
    src = mutate("AppointmentReminders", 'set status = "reminded"', 'set patient = "x"')
    assert "E401" in _codes(src, "AppointmentReminders")


def test_calendar_not_allowed():
    pol = mutate("RestaurantPolicy", "  allow calendar Tables\n", "")
    assert "E402" in _codes(pol, "ConfirmReservation")


def test_wait_over_30_days():
    src = mutate("QuoteFollowUp", "wait 3 days", "wait 45 days")
    assert "E501" in _codes(src, "QuoteFollowUp")


def test_names_are_bound_once():
    src = mutate("AppointmentReminders", "let tomorrows =", "let all =")
    assert "E601" in _codes(src, "AppointmentReminders")


def test_sms_to_email_is_type_error():
    src = mutate("LowSessionsRenewal", "draft email to s.parent_email subject \"Sessions running low\":",
                 "draft sms to s.parent_email:")
    assert "E601" in _codes(src, "LowSessionsRenewal")


def test_large_cap_warns_but_does_not_block():
    pol = mutate("ShopPolicy", "limit refund $50 per action", "limit refund $50 per action\n  limit order $900 per action")
    diags = check_text(block_defining("ProcessReturn"), "ProcessReturn", pol)
    assert "W201" in codes(diags)
    assert errors(diags) == []


def test_batch_preview_minimum():
    pol = mutate("ClinicBatchPolicy", "preview 5", "preview 2")
    assert "E703" in _codes(pol, "AppointmentRemindersBatch")


def test_batch_valid_over_24_hours():
    pol = mutate("ClinicBatchPolicy", "valid 1 hour", "valid 2 days")
    assert "E703" in _codes(pol, "AppointmentRemindersBatch")
