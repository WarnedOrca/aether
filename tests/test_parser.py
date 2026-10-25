import pytest

from checker import nodes as N
from checker.parser import AetherSyntaxError, parse_message, parse_source
from checker.spec_examples import load_examples


@pytest.fixture(scope="module")
def examples():
    return load_examples()


def test_all_spec_examples_parse(examples):
    # 15 numbered examples + the batch twin 1b
    assert len(examples.procedures) == 16
    assert "AppointmentRemindersBatch" in examples.procedures


def test_every_procedure_names_a_defined_policy(examples):
    for proc in examples.procedures.values():
        assert proc.policy in examples.policies, proc.name


def test_spec_policies_have_no_bad_lines(examples):
    for pol in examples.policies.values():
        assert pol.bad_lines == (), (pol.name, pol.bad_lines)


def test_keywords_can_be_column_names(examples):
    proc = examples.procedures["ConfirmReservation"]
    assert "at" in proc.sheets["Reservations"].columns
    proc = examples.procedures["FillCancelledSlot"]
    assert {"day", "time"} <= set(proc.sheets["Cancellations"].columns)


def test_interpolation_with_default():
    s = parse_message("Hi {a.patient default 'there'}, at {time_of(a.starts)}.")
    interps = [p for p in s.parts if isinstance(p, N.Interp)]
    assert interps[0].default == "there"
    assert interps[0].expr == N.Attr("a", "patient")
    assert isinstance(interps[1].expr, N.Call) and interps[1].default is None


def test_unbalanced_braces_rejected():
    with pytest.raises(AetherSyntaxError):
        parse_message("Hi {a.patient")


def test_unknown_policy_line_is_recorded_not_fatal():
    src = parse_source('policy P {\n  allow send without approval\n  limit sends 5 per day\n}')
    pol = src.policies["P"]
    assert [b.text for b in pol.bad_lines] == ["allow send without approval"]
    assert pol.rules[0].kind == "limit_sends"


def test_loop_without_bound_parses_for_checker_to_reject():
    src = parse_source(
        'procedure X { about "x" policy P sheet S "S" { a: Text } trigger every day at 09:00\n'
        "let t = fetch S\nfor each r in t { log \"hi\" } }"
    )
    loop = src.procedures["X"].body[1]
    assert isinstance(loop, N.ForEach) and loop.bound is None


def test_syntax_error_has_line():
    with pytest.raises(AetherSyntaxError) as exc:
        parse_source('procedure X { about "x" policy P trigger every day at 09:00\nlet = 3 }')
    assert exc.value.line == 2
