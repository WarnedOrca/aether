"""Tests for the 2026-10-27 stage 3 data fixes: tightened trap filter applied to existing data, trap-share seed order,
resume-config compatibility, and the seeded review sample. No GPU, no downloads."""

import json

import pytest

from stages.apply_trap_filter import apply_filter, flagged
from stages.stage3_paraphrase import (build_splits, config_compatible, seeds_digest, select_seeds, trap_ask_missing)


def rec(key, trap, sop, accepted=True):
    seed = key.split("#")[0]
    return {"key": key, "seed_id": seed, "trap": trap, "policy": "p", "sheets": "s", "program": "prog", "sop": sop,
            "accepted": accepted, "reject_reason": "" if accepted else "length",
            "provenance": {"model": "m", "hosted_ai_text": False, "seed_program": "data/x"}}


def write_dir(tmp_path, records):
    (tmp_path / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    rows = build_splits(records)
    for split, rs in rows.items():
        (tmp_path / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rs), encoding="utf-8")
    (tmp_path / "summary.json").write_text(json.dumps({"stage": 3, "records": len(records)}), encoding="utf-8")


def test_apply_filter_removes_only_flagged_trap_rows_and_keeps_provenance(tmp_path):
    good_trap = rec("a-1#0", "over-limit", "Order regardless of the total cost please")
    bad_trap = rec("a-2#0", "over-limit", "Order the supplies each Monday")  # no unsafe ask
    plain = rec("a-3#0", "none", "Order the supplies each Monday")  # plain wordings are never judged by the trap filter
    unchecked_kind = rec("a-4#0", "reveal-private", "anything")  # no reliable keyword for this kind
    rejected = rec("a-5#0", "over-limit", "x", accepted=False)
    records = [good_trap, bad_trap, plain, unchecked_kind, rejected]
    write_dir(tmp_path, records)
    before = build_splits(records)
    assert [r["key"] for r in flagged(records)] == ["a-2#0"]

    result = apply_filter(tmp_path)
    assert result["removed"] == ["a-2#0"]
    kept_ids = {json.loads(l)["id"] for s in ("train", "valid") for l in (tmp_path / f"{s}.jsonl").read_text().splitlines()}
    assert kept_ids == {"a-1#0", "a-3#0", "a-4#0"}
    assert len(kept_ids) == sum(len(v) for v in before.values()) - 1

    removed = [json.loads(l) for l in (tmp_path / "removed_rows.jsonl").read_text().splitlines()]
    assert len(removed) == 1 and removed[0]["key"] == "a-2#0"
    assert removed[0]["provenance"] == bad_trap["provenance"]  # provenance kept
    assert removed[0]["removed_reason"] == "trap ask missing"
    new_records = {json.loads(l)["key"]: json.loads(l) for l in (tmp_path / "records.jsonl").read_text().splitlines()}
    assert new_records["a-2#0"]["accepted"] is False and new_records["a-2#0"]["originally_accepted"] is True
    assert new_records["a-1#0"]["accepted"] is True
    assert (tmp_path / "records.before-trap-filter.jsonl").exists()
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["removed_by_tightened_trap_filter"] == 1 and summary["accepted"] == 3


def test_apply_filter_is_idempotent(tmp_path):
    write_dir(tmp_path, [rec("a-1#0", "unbounded", "send to everyone"), rec("a-2#0", "unbounded", "send the newsletter")])
    assert apply_filter(tmp_path)["removed"] == ["a-2#0"]
    snapshot = {p.name: p.read_bytes() for p in tmp_path.glob("*.jsonl")}
    assert apply_filter(tmp_path)["removed"] == []
    assert {p.name: p.read_bytes() for p in tmp_path.glob("*.jsonl")} == snapshot  # second run changes nothing


def test_apply_filter_refuses_when_flagged_set_differs_from_expected_list(tmp_path):
    write_dir(tmp_path, [rec("a-2#0", "unbounded", "send the newsletter")])
    with pytest.raises(ValueError, match="expected list"):
        apply_filter(tmp_path, expect_keys={"other#0"})
    assert (tmp_path / "records.jsonl").read_text() == json.dumps(rec("a-2#0", "unbounded", "send the newsletter")) + "\n"  # untouched


def test_real_data_28_flagged_rows_match_the_gate_file():
    """The committed quality-gate result lists the 28 rows the tightened filter flags; the filter must reproduce them,
    whether it is run on the original records (before the fix) or the fixed ones (then nothing is flagged and the gate's
    keys are all recorded as removed)."""
    from stages.common import ROOT
    gate = json.loads((ROOT / "eval/results/stage3-quality-gate-full-tightened-trap-filter-2026-10-26.json").read_text())
    expected = set(gate["checks"]["trap_ask_present"]["violations"])
    assert len(expected) == 28
    data = ROOT / "data/synthetic_v4"
    records = [json.loads(l) for l in (data / "records.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert not flagged(records), "data/synthetic_v4 still holds accepted rows that fail the tightened trap filter"
    by_key = {r["key"]: r for r in records}
    assert all(not by_key[k]["accepted"] and by_key[k]["originally_accepted"] for k in expected)
    train_ids = {json.loads(l)["id"] for s in ("train", "valid") for l in (data / f"{s}.jsonl").read_text(encoding="utf-8").splitlines()}
    assert not (expected & train_ids)
    assert all(not trap_ask_missing(json.loads(l)["trap"], json.loads(l)["sop"])
               for s in ("train", "valid") for l in (data / f"{s}.jsonl").read_text(encoding="utf-8").splitlines())
    removed = {json.loads(l)["key"] for l in (data / "removed_rows.jsonl").read_text(encoding="utf-8").splitlines()}
    assert expected <= removed


def seed_pool():
    return ([{"seed_id": f"p{i}", "trap": "none"} for i in range(300)]
            + [{"seed_id": f"t{i}", "trap": "x"} for i in range(60)])


def test_trap_share_order_keeps_prefix_and_target_share():
    pool = seed_pool()
    base = select_seeds(pool, 5, 0)
    order = select_seeds(pool, 5, 0, trap_share=0.25, fixed_prefix=40)
    assert order[:40] == base[:40]
    assert sorted(s["seed_id"] for s in order) == sorted(s["seed_id"] for s in pool)  # same programs, none lost or repeated
    for n in (100, 200, 240):
        share = sum(s["trap"] != "none" for s in order[:n]) / n
        assert abs(share - 0.25) < 0.03
    assert select_seeds(pool, 5, 120, trap_share=0.25, fixed_prefix=40) == order[:120]
    assert order == select_seeds(pool, 5, 0, trap_share=0.25, fixed_prefix=40)  # deterministic
    tail = order[-30:]
    assert all(s["trap"] == "none" for s in tail)  # traps ran out; plain programs follow


def test_trap_share_zero_keeps_old_behaviour():
    pool = seed_pool()
    assert select_seeds(pool, 5, 50) == select_seeds(pool, 5, 50, trap_share=0.0, fixed_prefix=10)


def test_resume_config_allows_longer_run_but_not_changed_wording_settings():
    pool = seed_pool()
    shuffled = select_seeds(pool, 5, 0)
    legacy = {"model": "m", "limit_programs": 100, "shuffle_seed": 5, "temperature": 0.9,
              "revision": "r", "prompt_version": "p2", "seeds_sha256": seeds_digest(shuffled[:100])}
    new = {"model": "m", "shuffle_seed": 5, "temperature": 0.9, "revision": "r", "prompt_version": "p2",
           "pool_sha256": seeds_digest(shuffled), "selection": {"limit_programs": 0, "trap_share": 0.27, "fixed_prefix": 100}}
    assert config_compatible(legacy, new, shuffled)  # old config format, extended run
    assert config_compatible(new, {**new, "selection": {"limit_programs": 500, "trap_share": 0.0, "fixed_prefix": 0}}, shuffled)
    assert not config_compatible(legacy, {**new, "temperature": 0.7}, shuffled)
    assert not config_compatible(legacy, {**new, "prompt_version": "p3"}, shuffled)
    assert not config_compatible({**legacy, "seeds_sha256": "0" * 64}, new, shuffled)  # different seed pool/order
    assert not config_compatible(new, {**new, "pool_sha256": "0" * 64}, shuffled)


def test_review_sample_is_seeded_and_not_hand_picked(tmp_path):
    from stages.review_sample import pick_sample
    rows = [{"id": f"s{i}#0", "sop": f"wording {i}", "trap": "none" if i % 4 else "over-limit"} for i in range(200)]
    a, b = pick_sample(rows, 30, 2026), pick_sample(rows, 30, 2026)
    assert a == b and len(a) == 30 and len({r["id"] for r in a}) == 30
    assert pick_sample(rows, 30, 7) != a
    assert [r["id"] for r in a] == sorted(r["id"] for r in a)  # listed in id order, not in draw order


def test_dev_report_counts_forbidden_columns_and_reused_about_lines():
    from eval.dev_report import about_line, forbidden_column, summarise
    rows = [
        {"set": "benchmark", "trap": "none", "parse": True, "check": False, "detail": "E401 reads column x", "safe_and_correct": False,
         "program": 'procedure A {\n  about "Remind patients"\n}'},
        {"set": "benchmark", "trap": "none", "parse": True, "check": True, "detail": "", "safe_and_correct": True,
         "program": 'procedure B {\n  about "Something new"\n}'},
        {"set": "benchmark", "trap": "over-limit", "parse": False, "check": False, "detail": "E401 but did not parse", "safe_and_correct": False,
         "program": ""},
        {"set": "heldout3", "trap": "none", "parse": True, "check": True, "detail": "", "safe_and_correct": True, "program": 'about "Remind patients"'},
    ]
    assert about_line(rows[0]["program"]) == "Remind patients" and about_line("") is None
    assert forbidden_column(rows[0]) and not forbidden_column(rows[1]) and not forbidden_column(rows[2])
    s = summarise(rows, {"train": {"Remind patients"}})
    assert (s["n"], s["correct"], s["non_trap_correct"], s["trap_correct"]) == (3, 1, 1, 0)  # non-benchmark rows are ignored
    assert s["forbidden_column_all"] == 1 and s["forbidden_column_non_trap_failures"] == 1
    assert s["about_reused_train"] == 1


def test_repair_run_saves_each_task_and_resumes(tmp_path):
    """eval.repair: an interrupted run keeps finished tasks; rerunning the same command finishes the rest only."""
    import argparse
    from eval import repair
    from eval.bench import load_tasks
    tasks = load_tasks()
    refs = {t.sop: t.program for t in tasks}
    plain = tmp_path / "plain.jsonl"  # every plain output is unparseable, so every task needs a repair round
    plain.write_text("".join(json.dumps({"set": "benchmark", "id": t.id, "trap": t.trap, "raw": "nonsense", "parse": False,
                                         "check": False, "exec": False, "safe_and_correct": False}) + "\n" for t in tasks))
    calls = {"n": 0}

    class FakeGen:  # answers with the reference program; can be told to crash after N generations
        crash_after = None

        def __init__(self, *a):
            pass

        def prompt_text(self, msgs):
            return msgs[0]["content"] if len(msgs) == 1 else next(m["content"] for m in msgs if m["role"] == "user")

        def generate(self, prompts):
            calls["n"] += 1
            if self.crash_after is not None and calls["n"] > self.crash_after:
                raise RuntimeError("simulated shutdown")
            sop_task = next(t for t in tasks if t.sop in prompts[0])
            return ["```aether\n" + refs[sop_task.sop] + "\n```"]

    args = argparse.Namespace(adapter=None, model="fake", plain=str(plain), tasks_dir="eval/benchmark", label="t",
                              rounds=3, fewshot=0, out=str(tmp_path / "rep"))
    FakeGen.crash_after = 5
    with pytest.raises(RuntimeError):
        repair.run(args, FakeGen)
    partial = (tmp_path / "rep.partial.jsonl").read_text().splitlines()
    assert len(partial) == 5 and not (tmp_path / "rep.json").exists()
    FakeGen.crash_after = None
    calls["n"] = 0
    summary = repair.run(args, FakeGen)
    assert calls["n"] == len(tasks) - 5  # finished tasks were not regenerated
    assert summary["n"] == len(tasks) and summary["plain_correct"] == 0
    rows = [json.loads(l) for l in (tmp_path / "rep.jsonl").read_text().splitlines()]
    assert [r["id"] for r in rows] == [t.id for t in tasks] and all(r["rounds_used"] == 1 for r in rows)
    with pytest.raises(ValueError, match="different settings"):
        repair.run(argparse.Namespace(**{**vars(args), "rounds": 2}), FakeGen)
