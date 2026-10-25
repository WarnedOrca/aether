import pytest

from checker.mutate import block_defining
from checker.parser import parse_source
from checker.render import render, safety_summary
from checker.spec_examples import load_examples

EX = load_examples()


@pytest.mark.parametrize("name", sorted(EX.procedures))
def test_every_example_renders(name):
    proc = EX.procedures[name]
    out = render(proc, EX.policies[proc.policy])
    assert out.startswith(name)
    assert "Safety summary:" in out
    assert "?" not in out.replace("?\"", "")  # no unrendered expressions


def test_rendering_is_deterministic():
    proc = EX.procedures["AppointmentReminders"]
    pol = EX.policies["ClinicPolicy"]
    assert render(proc, pol) == render(proc, pol)


def test_example1_mentions_default_and_approval():
    proc = EX.procedures["AppointmentReminders"]
    out = render(proc, EX.policies["ClinicPolicy"])
    assert "{patient, or 'there' if blank}" in out
    assert "Ask you to approve this message" in out
    assert "at most 100 of them" in out


def test_safety_summary_lists_caps_and_privacy():
    proc = EX.procedures["ProcessReturn"]
    lines = safety_summary(proc, EX.policies["ShopPolicy"])
    joined = "\n".join(lines)
    assert "Refunds over $15.00 need your OK; no refund over $50.00 ever; at most $300.00 per day." in joined
    clinic = "\n".join(safety_summary(EX.procedures["AppointmentReminders"], EX.policies["ClinicPolicy"]))
    assert "Never put in a message: Appointments.reason." in clinic
    assert "Approval: per message" in clinic


def test_safety_summary_prints_large_cap_warning():
    src = block_defining("ProcessReturn").replace("limit refund $300 per day", "limit refund $5000 per day")
    parsed = parse_source(src)
    lines = safety_summary(parsed.procedures["ProcessReturn"], parsed.policies["ShopPolicy"])
    assert any(line.startswith("WARNING: large cap") for line in lines)
