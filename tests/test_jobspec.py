"""Job spec schema and compiler: every compiled program passes the parser, the checker and a monitored dry run on
made-up rows; the page's config matches the spec; refusals and invalid specs are never compiled."""

from datetime import timedelta
from decimal import Decimal

import pytest

from interpreter.sandbox import DEFAULT_NOW
from interpreter.values import EMPTY, Money
from jobspec.compile import SpecError, aether_program, dry_run, tool_config
from jobspec.spec import TEMPLATE_NAMES, canonical, default_spec, parse_output, problems

TODAY = DEFAULT_NOW.date()
DUE = {"appointment_reminder": TODAY + timedelta(days=1), "follow_up": TODAY - timedelta(days=1),
       "review_request": TODAY - timedelta(days=2), "invoice_nudge": TODAY - timedelta(days=10)}


def fake_rows(template, channel):
    """Made-up rows: two due, one opted out, one contacted yesterday, one not due."""
    contact = (lambda i: f"+1555010{i}") if channel == "sms" else (lambda i: f"fake{i}@example.com")
    to = "phone" if channel == "sms" else "email"
    base = lambda i, **kw: {"name": f"Fake Customer {i}", to: contact(i), "date": DUE[template], "opted_out": EMPTY,
                            "last_contacted": EMPTY, **({"invoice": f"INV-TEST-{i}", "amount": Money(Decimal("40.00"))}
                                                        if template == "invoice_nudge" else {}), **kw}
    return [base(1), base(2, opted_out="no"), base(3, opted_out="yes"),
            base(4, last_contacted=TODAY - timedelta(days=1)), base(5, date=TODAY + timedelta(days=40))]


@pytest.mark.parametrize("template", TEMPLATE_NAMES)
@pytest.mark.parametrize("channel", ["sms", "email"])
def test_compiled_program_checks_and_dry_runs_clean(template, channel):
    spec = dict(default_spec(template), channel=channel, min_days_since_contact=7, daily_limit=10)
    r = dry_run(spec, fake_rows(template, channel))
    assert r["monitor_problems"] == []
    assert r["status"] == "ok"
    names = sorted(e["body"].split(",")[0] for e in r["delivered"])
    assert names == ["Hi Fake Customer 1", "Hi Fake Customer 2"]  # opted out, recently contacted and not-due rows skipped
    assert all(e["channel"] == channel for e in r["delivered"])


def test_daily_limit_is_in_the_program():
    spec = dict(default_spec("follow_up"), daily_limit=1, min_days_since_contact=0)
    r = dry_run(spec, fake_rows("follow_up", "sms"))
    assert len(r["delivered"]) == 1 and r["monitor_problems"] == []
    assert "limit sends 1 per day" in aether_program(spec) and "up to 1 {" in aether_program(spec)


def test_tool_config_matches_spec_and_is_deterministic():
    spec = {"template": "invoice_nudge", "channel": "email", "min_days_since_contact": 14, "send_window": ["10:00", "17:30"],
            "daily_limit": 25}
    a, b = tool_config(spec, business="Test Business"), tool_config(spec, business="Test Business")
    assert a == b and aether_program(spec) == aether_program(spec)
    assert (a["channel"], a["min_days_since_contact"], a["window"], a["daily_limit"], a["date_mode"]) == ("email", 14, ["10:00", "17:30"], 25, "overdue")
    assert a["map"]["opted_out"] == "opted_out" and a["extra"] == {"business": "Test Business"}
    assert "send only between 10:00 and 17:30" in aether_program(spec)


@pytest.mark.parametrize("bad", [
    {"refuse": "contact_opted_out"},
    {"refuse": "because"},
    dict(default_spec("follow_up"), daily_limit=500),
    dict(default_spec("follow_up"), daily_limit=0),
    dict(default_spec("follow_up"), send_window=["21:00", "08:00"]),
    dict(default_spec("follow_up"), send_window=["9am", "5pm"]),
    dict(default_spec("follow_up"), template="instagram_post"),
    dict(default_spec("follow_up"), skip_opted_out=False),
    dict(default_spec("follow_up"), min_days_since_contact=True),
])
def test_refusals_and_invalid_specs_are_never_compiled(bad):
    with pytest.raises(SpecError):
        aether_program(bad)
    with pytest.raises(SpecError):
        tool_config(bad)


def test_schema_helpers():
    assert problems({"refuse": "unsupported_job"}) == []
    assert problems(default_spec("review_request")) == []
    assert problems("text") == ["not a JSON object"]
    assert canonical({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'
    assert parse_output('sure: {"refuse": "no_daily_limit"} ok') == {"refuse": "no_daily_limit"}
    assert parse_output("no json here") is None
    assert parse_output('{"a": {"b": 1}}') == {"a": {"b": 1}}
