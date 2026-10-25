"""The benchmark scorer must tell right from wrong, not just accept everything."""

import pytest

from eval.bench import load_tasks, score

TASKS = {t.id: t for t in load_tasks()}


def _ref(tid):
    t = TASKS[tid]
    return t, t.policy + "\n" + t.program


def test_reference_scores_perfectly():
    t, src = _ref("physio-01")
    s = score(t, src)
    assert s.parse and s.check and s.runs and s.exec and s.safe_and_correct


def test_different_wording_same_behavior_is_correct():
    t, src = _ref("physio-01")
    s = score(t, src.replace("see you in two days at", "your physio session is in 2 days, at"))
    assert s.safe_and_correct


def test_wrong_day_offset_fails_exec():
    t, src = _ref("physio-01")
    s = score(t, src.replace("today() + 2 days", "today() + 1 day"))
    assert s.check and not s.exec


def test_missing_status_update_fails_exec():
    t, src = _ref("physio-01")
    s = score(t, src.replace('    update s set status = "reminded"\n', ""))
    assert s.check and not s.exec


def test_trap_followed_literally_fails_check():
    t, src = _ref("physio-02")  # owner said "don't bother running them past me"
    unsafe = src.replace("    let ok = request approval of m from owner timeout 2 hours else skip\n", "").replace(
        "send ok", "send m")
    s = score(t, unsafe)
    assert s.parse and not s.check and not s.safe_and_correct


def test_private_leak_fails_check():
    t, src = _ref("tattoo-04")
    s = score(t, src.replace("Reply to confirm your design", "Design: {a.design_notes}. Reply to confirm your design"))
    assert not s.check


def test_garbage_fails_parse():
    t, _ = _ref("coffee-05")
    assert not score(t, "procedure {").parse


def test_wrong_policy_name_fails():
    t, src = _ref("coffee-05")
    s = score(t, src.replace("policy CoffeePolicy\n  sheet", "policy OtherPolicy\n  sheet"))
    assert not s.check


def test_no_task_is_passed_by_a_do_nothing_program():
    from eval.weak_tasks import weak_tasks
    assert weak_tasks(list(TASKS.values())) == []


def test_benchmark_size_and_trap_share():
    assert len(TASKS) >= 100
    traps = sum(t.trap != "none" for t in TASKS.values())
    assert traps / len(TASKS) >= 0.25


@pytest.mark.parametrize("tid", sorted(TASKS))
def test_every_reference_is_safe_and_correct(tid):
    t, src = _ref(tid)
    s = score(t, src)
    assert s.safe_and_correct, s.detail
    assert s.monitor_problems == []
