"""The prefix checker must accept every prefix of a valid program and reject clear errors."""

from eval.bench import load_tasks
from eval.constrained import complete, valid_prefix


def test_every_prefix_of_reference_programs_is_valid():
    tasks = load_tasks()[:12]
    for t in tasks:
        prog = t.program
        bad = [i for i in range(1, len(prog) + 1, 3) if not valid_prefix(prog[:i])]
        assert not bad, (t.id, repr(prog[max(0, bad[0] - 30):bad[0]]))
        assert complete(prog)


def test_clear_errors_rejected():
    assert not valid_prefix('procedure X {\n  about "x"\n  policy P\n  trigger every Thursday at')
    assert not valid_prefix('procedure X {\n  about "x"\n  policy P\n  trigger every day at 09:00\n  let = ')
    assert not valid_prefix('procedure X {\n  about "x"\n  policy P\n  trigger every morning')


def test_partial_tokens_accepted():
    assert valid_prefix('procedure X {\n  ab')
    assert valid_prefix('procedure X {\n  about "half a str')
    assert valid_prefix('procedure X {\n  about "x"\n  policy P\n  trigger every mon')
