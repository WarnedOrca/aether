"""Mutation testing of the checker: every single-rule-breaking mutant must be rejected."""

from checker.mutate import mutants, run_mutants


def test_mutation_operators_produce_mutants():
    assert len(mutants("AppointmentReminders")) >= 4


def test_every_mutant_rejected_with_expected_code():
    rows = run_mutants()
    survivors = [r for r in rows if not r["expected_found"]]
    assert survivors == []
    assert all(r["parsed"] for r in rows)  # mutants must be real programs, not parse failures
