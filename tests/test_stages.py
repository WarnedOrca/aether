"""Unit tests for the stage 3-5 helpers that must work unattended (no GPU, no downloads)."""

import json
import logging
import pytest

from stages.common import JsonlCheckpoint
from stages.stage3_paraphrase import invented_numbers, missing_times, numbers_needed, select_seeds, trap_ask_missing
from stages.stage5_eval import holm


def test_offline_metadata_and_loading_never_query_hub(monkeypatch, tmp_path):
    from stages import common
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setattr(common, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        common.check_license("test", logging.getLogger())
    (tmp_path / "models.lock.json").write_text(json.dumps({"models": {
        "test": {"license": "apache-2.0", "revision": "abc123"}}}))
    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "model_info", lambda *a, **k: pytest.fail("network used"))
    assert common.check_license("test", logging.getLogger()) == "apache-2.0"
    assert common.model_revision("test") == "abc123"
    assert common.model_load_kwargs("test") == {"revision": "abc123", "local_files_only": True}
    (tmp_path / "models.lock.json").write_text(json.dumps({"models": {
        "test": {"license": "unknown", "revision": "abc123"}}}))
    with pytest.raises(ValueError):
        common.model_load_kwargs("test")


def test_online_loading_behavior_unchanged(monkeypatch):
    from stages.common import model_load_kwargs
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    assert model_load_kwargs("unlocked-online-model") == {}


def test_partial_accumulation_group():
    from stages.stage4_qlora import accumulation_size
    assert [accumulation_size(k, 5, 4) for k in range(5)] == [4, 4, 4, 4, 1]


def test_snapshot_requires_matching_revision_and_all_shards(monkeypatch, tmp_path):
    import huggingface_hub
    from stages import preflight
    path = tmp_path / "abc123full"
    path.mkdir()
    monkeypatch.setattr(preflight, "locked_model", lambda m: {"revision": "abc123"})
    monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda *a, **kw: str(path))
    for name in ("config.json", "tokenizer_config.json", "tokenizer.json"):
        (path / name).write_text("{}")
    (path / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {"x": "shard.safetensors"}}))
    with pytest.raises(ValueError, match="shard"):
        preflight.snapshot("test")
    (path / "shard.safetensors").write_bytes(b"test")
    assert preflight.snapshot("test") == str(path)
    monkeypatch.setattr(preflight, "locked_model", lambda m: {"revision": "different"})
    with pytest.raises(ValueError, match="mismatch"):
        preflight.snapshot("test")


def test_checkpoint_resumes_and_drops_partial_line(tmp_path):
    p = tmp_path / "records.jsonl"
    p.write_text(json.dumps({"key": "a"}) + "\n" + json.dumps({"key": "b"}) + "\n" + '{"key": "c", "tru', encoding="utf-8")
    ck = JsonlCheckpoint(p)
    assert ck.done == {"a", "b"}
    ck.add({"key": "c"})
    ck.close()
    assert [json.loads(x)["key"] for x in p.read_text(encoding="utf-8").splitlines()] == ["a", "b", "c"]


def test_checkpoint_does_not_discard_interior_corruption(tmp_path):
    p = tmp_path / "records.jsonl"
    original = '{"key":"a"}\nbroken\n{"key":"b"}\n'
    p.write_text(original)
    with pytest.raises(ValueError, match="Corrupt"):
        JsonlCheckpoint(p)
    assert p.read_text() == original


def test_wording_must_state_caps_amounts_and_times():
    prog = "trigger every day at 18:00\n for each x in y up to 15 {\n if cost > $200.00 {"
    assert numbers_needed(prog) == {"15", "200"}
    assert numbers_needed("if credit > $0.00 { for each r in x up to 20 {") == {"20"}
    assert missing_times(prog, "every evening at 6pm") == []
    assert missing_times(prog, "at 18:00") == []
    assert missing_times(prog, "every evening") == ["18:00"]
    assert missing_times("at 12:00", "at noon") == []
    assert missing_times("at 18:00", "at 6am") == ["18:00"]
    assert missing_times("at 18:30", "at 6pm") == ["18:30"]
    assert missing_times("at 08:00", "at 08:00") == []


def test_invented_numbers_and_trap_ask():
    src = "trigger every day at 18:00\n for each x in y up to 20 {\n timeout 6 hours\n cost > $200.00\n code RETURN20\n at 08:30"
    assert invented_numbers(src, "every day at 6 PM, up to 20, $200, within 6 hours, 8:30 am, 6:00 pm, code RETURN20") == []
    assert invented_numbers(src, "clients from the last 45 days, max 20") == ["45"]
    assert invented_numbers("up to 05", "up to 5") == []
    assert trap_ask_missing("unsupported-post", "Please post a shout-out on Instagram") is False
    assert trap_ask_missing("unsupported-post", "Please list the students for me") is True
    assert trap_ask_missing("unsupported-charge", "charge their cards automatically") is False
    assert trap_ask_missing("over-limit", "order regardless of cost") is False
    assert trap_ask_missing("over-limit", "order the supplies") is True
    assert trap_ask_missing("skip-approval", "don't bother asking me first") is False
    assert trap_ask_missing("none", "anything") is False
    assert trap_ask_missing("reveal-private", "anything") is False  # no reliable keyword: not checked


def test_seed_selection_is_deterministic_and_mixes_sources():
    seeds = [{"seed_id": f"a{i}", "trap": "none"} for i in range(50)] + [{"seed_id": f"t{i}", "trap": "x"} for i in range(50)]
    assert select_seeds(seeds, 0, 10) == seeds[:10]  # shuffle off: old behaviour (first N)
    a, b = select_seeds(seeds, 11, 20), select_seeds(seeds, 11, 20)
    assert a == b and len(a) == 20
    assert {s["trap"] for s in a} == {"none", "x"}
    assert select_seeds(seeds, 12, 20) != a
    assert len(select_seeds(seeds, 11, 0)) == 100  # limit 0 = all programs


def test_holm_adjustment():
    assert holm([0.04, 0.01]) == [0.04, 0.02]
    assert holm([0.3, 0.6]) == [0.6, 0.6]


def test_final_eval_requires_all_tasks_and_monitor_evidence(tmp_path):
    from stages.stage5_eval import require_complete
    p = tmp_path / "run.jsonl"
    p.write_text(json.dumps({"id": "a", "safe_and_correct": True, "trap": "none"}) + "\n")
    with pytest.raises(ValueError, match="Incomplete"):
        require_complete(p, "plain", {"a", "b"})
    p.with_suffix(".json").write_text("{}")
    with pytest.raises(ValueError, match="monitor"):
        require_complete(p, "plain", {"a"})
    p.with_suffix(".json").write_text('{"monitor_problems_total": 0}')
    require_complete(p, "plain", {"a"})


def test_answer_only_loss_matches_full_loss():
    torch = pytest.importorskip("torch")
    from transformers import Qwen2Config, Qwen2ForCausalLM
    from stages.stage4_qlora import answer_only_loss
    torch.manual_seed(0)
    model = Qwen2ForCausalLM(Qwen2Config(vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                                         num_attention_heads=2, num_key_value_heads=2, max_position_embeddings=64))
    ids = torch.randint(0, 64, (2, 20))
    mask = torch.ones_like(ids)
    mask[1, 17:] = 0  # right padding on the second row
    labels = ids.clone()
    labels[0, :9] = -100
    labels[1, :6] = -100
    labels[1, 17:] = -100
    full = model(input_ids=ids, attention_mask=mask, labels=labels).loss
    fast = answer_only_loss(model, ids, labels, mask)
    assert torch.allclose(full, fast, atol=1e-5)
    fast.backward()  # gradients flow


def test_answer_only_valid_loss_matches_finetune_evaluate(monkeypatch):
    torch = pytest.importorskip("torch")
    from transformers import Qwen2Config, Qwen2ForCausalLM
    from stages import stage4_qlora
    from training.finetune import evaluate
    monkeypatch.setattr(torch.Tensor, "cuda", lambda self, *a, **k: self)  # CPU-only test
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: None)
    torch.manual_seed(0)
    model = Qwen2ForCausalLM(Qwen2Config(vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                                         num_attention_heads=2, num_key_value_heads=2, max_position_embeddings=64))
    items = []
    for n, k in ((12, 5), (18, 9), (9, 3)):  # (length, prompt tokens): different answer lengths weight differently
        ids = torch.randint(0, 64, (n,)).tolist()
        items.append({"input_ids": ids, "labels": [-100] * k + ids[k:]})
    expected = evaluate(model, items, 2, 0, torch)
    got = stage4_qlora.answer_only_valid_loss(model, items, 2, 0)
    assert abs(expected - got) < 1e-5


def test_stage5_resume_rules_and_fixed_output_paths(tmp_path, monkeypatch):
    from stages import stage5_eval as s5
    monkeypatch.setattr(s5, "ROOT", tmp_path)
    (tmp_path / "eval/results").mkdir(parents=True)
    plain = {"name": "v0.2-plain", "kind": "plain", "model": "m"}
    rep = {"name": "v0.2-repaired", "kind": "repair", "model": "m", "plain_of": "v0.2-plain"}
    for c in (plain, rep):  # the fixed output path is what result_file looks for
        base = s5.out_path(c)
        base.with_name(base.name + ".jsonl").write_text("{}")
        base.with_name(base.name + ".partial.jsonl").write_text("{}")
        assert s5.result_file(c) is None  # no summary .json yet: not complete
        base.with_name(base.name + ".json").write_text("{}")
        assert s5.result_file(c) == base.with_name(base.name + ".jsonl")
    marker = tmp_path / "x.started.json"
    assert s5.may_resume(marker, ["a"], "h") is False
    marker.write_text(json.dumps({"command": ["a"], "conditions_sha256": "h"}))
    assert s5.may_resume(marker, ["a"], "h") is True
    with pytest.raises(ValueError, match="different command"):
        s5.may_resume(marker, ["b"], "h")
    with pytest.raises(ValueError, match="different command"):
        s5.may_resume(marker, ["a"], "other")


def test_stage5_without_confirmatory_reports_all_exploratory(tmp_path, monkeypatch):
    import subprocess
    from types import SimpleNamespace
    from stages import stage5_eval as s5
    import eval.bench
    monkeypatch.setattr(s5, "ROOT", tmp_path)
    monkeypatch.setattr(s5, "OUT", tmp_path / "eval/results/stage5")
    (tmp_path / "eval/results").mkdir(parents=True)
    spec = {"_confirmatory_note": "declared comparison needs a stage-4 model", "confirmatory": None, "conditions": [
        {"name": "base-fewshot", "kind": "plain", "model": "m", "fewshot": 1},
        {"name": "v0.2-plain", "kind": "plain", "model": "m", "adapter": "a"},
        {"name": "v0.2-repaired", "kind": "repair", "plain_of": "v0.2-plain", "model": "m", "adapter": "a"}]}
    spec_path = tmp_path / "conds.json"
    spec_path.write_text(json.dumps(spec))
    ids = [("t1", "none"), ("t2", "none"), ("t3", "over-limit")]
    monkeypatch.setattr(eval.bench, "load_tasks", lambda d: [SimpleNamespace(id=i, trap=t) for i, t in ids])
    monkeypatch.setattr(s5, "check_license", lambda m, log: "apache-2.0")
    real_check_output = subprocess.check_output
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: spec_path.read_bytes() if a and a[0][:2] == ["git", "show"] else real_check_output(*a, **k))
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("--out") + 1]
        repair = "eval.repair" in cmd
        with open(out + ".jsonl", "w") as f:
            for n, (i, t) in enumerate(ids):
                ok = n == 0
                f.write(json.dumps({"id": i, "trap": t, **({"repaired": {"safe_and_correct": ok}} if repair else {"safe_and_correct": ok})}) + "\n")
        open(out + ".json", "w").write(json.dumps({"monitor_problems_total": 0}))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("sys.argv", ["stage5", "--conditions", "conds.json"])
    s5.main()
    summary = json.loads((tmp_path / "eval/results/stage5/summary.json").read_text())
    assert summary["confirmatory"] is None and "stage-4 model" in summary["note"]
    assert all(c["status"] == "exploratory" for c in summary["conditions"].values())
    assert summary["conditions"]["v0.2-plain"]["non_trap"]["correct"] == 1 and summary["conditions"]["v0.2-plain"]["trap"]["n"] == 1
    assert len(calls) == 3
    s5.main()  # rerun after finishing: nothing runs again
    assert len(calls) == 3


def test_stage5_posthoc_paired_counts():
    from eval.stage5_posthoc import paired
    a = {"t1": True, "t2": False, "t3": False, "t4": True}
    b = {"t1": True, "t2": True, "t3": True, "t4": False}
    r = paired("a", a, "b", b)
    assert (r["a_correct"], r["b_correct"], r["a_only_correct"], r["b_only_correct"]) == (2, 3, 1, 2)
    assert r["mcnemar_exact_p"] == 1.0
    with pytest.raises(ValueError, match="different tasks"):
        paired("a", a, "b", {"t1": True})
