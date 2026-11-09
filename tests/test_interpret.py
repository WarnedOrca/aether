"""Interpreter interface, model fallback, the settings-file CLI, and the page's settings import check.
Fake sentences and a fake model only (no GPU)."""

import json

import pytest

from jobspec.interpret import (KeywordInterpreter, LocalModelInterpreter, _script_sentence, build_messages,
                               EXAMPLE_SPECS, interpret)
from jobspec.make_settings import main as make_settings
from jobspec.spec import default_spec
from jobspec.validate import REFUSAL_REASON, check_spec
from tests.test_tool import run_js

GOOD = dict(default_spec("review_request"), channel="email", daily_limit=15)


def fake(text):
    return LocalModelInterpreter(lambda msgs: text, "fake/model")


def test_model_result_used_when_valid():
    r = interpret("Fake sentence about reviews", fake("Sure: " + json.dumps(GOOD)))
    assert r.accepted and r.spec == GOOD and r.source == "local_model:fake/model" and r.notes == []


@pytest.mark.parametrize("raw", ["no json at all", json.dumps(dict(GOOD, daily_limit=500)),
                                 json.dumps(dict(GOOD, send_window=["22:00", "06:00"])), '{"refuse": "because"}',
                                 json.dumps(dict(GOOD, skip_opted_out=False))])
def test_bad_model_output_falls_back_to_keyword(raw):
    r = interpret("Remind customers by text from 9am to 6pm", fake(raw))
    assert r.source == "keyword" and r.accepted and r.spec["template"] == "appointment_reminder"
    assert "model result not used" in r.notes[0]


def test_model_crash_falls_back_and_says_so():
    def boom(msgs):
        raise RuntimeError("fake GPU failure")
    r = interpret("Remind customers by text", LocalModelInterpreter(boom))
    assert r.source == "keyword" and "model failed (RuntimeError)" in r.notes[0]


def test_model_refusal_is_kept_with_plain_reason():
    r = interpret("Remind customers by text", fake('{"refuse": "contact_opted_out"}'))
    assert r.source.startswith("local_model") and not r.accepted and r.spec is None
    assert r.reason == REFUSAL_REASON["contact_opted_out"]


def test_keyword_refusal_has_plain_reason():
    r = KeywordInterpreter().interpret("Text everyone, even the ones who opted out")
    assert not r.accepted and "opted out" in r.reason


def test_check_spec_rejects_invalid_and_accepts_valid():
    assert check_spec(GOOD) == (True, "")
    ok, why = check_spec(dict(GOOD, daily_limit=0))
    assert not ok and why.startswith("invalid settings")


def test_prompt_examples_are_script_made_and_valid():
    msgs = build_messages("x")
    assert msgs[-1] == {"role": "user", "content": "x"} and len(msgs) == 2 + 2 * len(EXAMPLE_SPECS)
    for s in EXAMPLE_SPECS:
        assert check_spec(s)[0] and _script_sentence(s)


def test_cli_writes_settings_file_and_page_accepts_it(tmp_path, capsys):
    out = tmp_path / "s.json"
    assert make_settings(["Remind customers by text from 9am to 6pm, at most 40 a day", "--out", str(out), "--no-model"]) == 0
    obj = json.loads(out.read_text(encoding="utf-8"))
    assert obj["produced_by"] == "keyword" and obj["settings"]["daily_limit"] == 40 and obj["format"] == "draft-pack-settings"
    assert "Produced by: keyword" in capsys.readouterr().out
    assert run_js(f"console.log(JSON.stringify(Core.checkSettings({json.dumps(obj)})))") == []
    bad = dict(obj, settings=dict(obj["settings"], daily_limit=900))
    assert run_js(f"console.log(JSON.stringify(Core.checkSettings({json.dumps(bad)})))") == ["daily limit must be a whole number 1-200"]
    extra = dict(obj, settings=dict(obj["settings"], skip_opted_out=False))
    assert run_js(f"console.log(JSON.stringify(Core.checkSettings({json.dumps(extra)})))")


def test_cli_refusal_writes_nothing(tmp_path):
    out = tmp_path / "s.json"
    assert make_settings(["Text the opted out customers too", "--out", str(out), "--no-model"]) == 2
    assert not out.exists()


def test_compare_suggestion():
    got = run_js('console.log(JSON.stringify(Core.compareSuggestion({daily_limit: 40, send_window: ["09:00","18:00"]}, {daily_limit: 30, send_window: ["09:00","18:00"]})))')
    assert got == [{"field": "daily_limit", "outcome": "edited"}, {"field": "send_window", "outcome": "accepted_unchanged"}]
