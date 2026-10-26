"""Unit tests for the stage 3-5 helpers that must work unattended (no GPU, no downloads)."""

import json
import logging
import pytest

from stages.common import JsonlCheckpoint
from stages.stage3_paraphrase import missing_times, numbers_needed
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


def test_gpu_check_fails_on_existing_job_and_low_memory(monkeypatch):
    from stages import preflight
    monkeypatch.setattr(preflight, "smi", lambda *a: "9000")
    with pytest.raises(ValueError, match="10 GiB"):
        preflight.gpu_free()
    monkeypatch.setattr(preflight, "smi", lambda *a: "123, python.exe")
    with pytest.raises(ValueError, match="already running"):
        preflight.gpu_idle()


def test_wording_must_state_caps_amounts_and_times():
    prog = "trigger every day at 18:00\n for each x in y up to 15 {\n if cost > $200.00 {"
    assert numbers_needed(prog) == {"15", "200"}
    assert missing_times(prog, "every evening at 6pm") == []
    assert missing_times(prog, "at 18:00") == []
    assert missing_times(prog, "every evening") == ["18:00"]
    assert missing_times("at 12:00", "at noon") == []
    assert missing_times("at 18:00", "at 6am") == ["18:00"]
    assert missing_times("at 18:30", "at 6pm") == ["18:30"]
    assert missing_times("at 08:00", "at 08:00") == []


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
