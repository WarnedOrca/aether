"""Unit tests for the stage 3-5 helpers that must work unattended (no GPU, no downloads)."""

import json

from stages.common import JsonlCheckpoint
from stages.stage3_paraphrase import missing_times, numbers_needed
from stages.stage5_eval import holm


def test_checkpoint_resumes_and_drops_partial_line(tmp_path):
    p = tmp_path / "records.jsonl"
    p.write_text(json.dumps({"key": "a"}) + "\n" + json.dumps({"key": "b"}) + "\n" + '{"key": "c", "tru', encoding="utf-8")
    ck = JsonlCheckpoint(p)
    assert ck.done == {"a", "b"}
    ck.add({"key": "c"})
    ck.close()
    assert [json.loads(x)["key"] for x in p.read_text(encoding="utf-8").splitlines()] == ["a", "b", "c"]


def test_wording_must_state_caps_amounts_and_times():
    prog = "trigger every day at 18:00\n for each x in y up to 15 {\n if cost > $200.00 {"
    assert numbers_needed(prog) == {"15", "200"}
    assert missing_times(prog, "every evening at 6pm") == []
    assert missing_times(prog, "at 18:00") == []
    assert missing_times(prog, "every evening") == ["18:00"]
    assert missing_times("at 12:00", "at noon") == []


def test_holm_adjustment():
    assert holm([0.04, 0.01]) == [0.04, 0.02]
    assert holm([0.3, 0.6]) == [0.6, 0.6]
