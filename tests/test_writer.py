"""AI message writer: script checks on every wording, regenerate-on-reject, file format, and agreement with the page's
Core.checkTemplate. Fake model outputs and made-up wordings only."""

import json

import pytest

from jobspec.spec import TEMPLATES
from jobspec.writer import REQUIRED, check_template, templates_file, write_templates
from tests.test_tool import run_js

CASES = [
    ("Hi {name}, thanks for choosing {business}. A review would help: {review_link}", "review_request"),
    ("Hi {name}, {business} here. Get 20% off your next visit! {review_link}", "review_request"),
    ("Hi {name}, review {business} at www.example.com {review_link}", "review_request"),
    ("Hi {name}, our treatment at {business} is guaranteed to heal you. {review_link}", "review_request"),
    ("Hi {name}, see you on {date} at {business}. Reply to change it.", "appointment_reminder"),
    ("Hi {name}, see you on {date}.", "appointment_reminder"),
    ("Hi {name}, see you on {date} at {business}, {phone}.", "appointment_reminder"),
    ("Hi {name}, invoice {invoice} for {amount} was due {date}. Feel free to reply with questions.", "invoice_nudge"),
    ("Hi {name}, invoice {invoice} for {amount} was due {date}. Pay $40 now.", "invoice_nudge"),
    ("Hi {name}, thanks for visiting {business} on {date}! Free gift next time.", "follow_up"),
    ("Hi {name}, thanks for visiting {business} on {date} {", "follow_up"),
    ("Hi {name}, email us at hello@example.com about {business} {date}", "follow_up"),
    ("x" * 400 + "{name}{business}{date}", "follow_up"),
    ("", "follow_up"),
    ("Hi {name}, it was a deal to see you at {business} on {date}.", "follow_up"),
]


def test_check_template_rules():
    ok = [t for t, job in CASES if not check_template(t, job)]
    assert ok == [CASES[0][0], CASES[4][0], CASES[7][0]]
    assert "missing placeholders: business" in check_template(CASES[5][0], "appointment_reminder")
    assert any("not allowed" in p for p in check_template(CASES[6][0], "appointment_reminder"))


def test_builtin_templates_pass():
    for job, t in TEMPLATES.items():
        assert check_template(t["text"], job) == [], job
        assert set(REQUIRED[job]) <= set(__import__("re").findall(r"\{(\w+)\}", t["text"]))


def test_page_and_python_agree():
    js = run_js("console.log(JSON.stringify(" + json.dumps(CASES) + ".map(([t, j]) => Core.checkTemplate(t, j))))")
    assert js == [check_template(t, j) for t, j in CASES]


def test_regenerates_until_three_valid_and_records_attempts():
    outputs = iter([
        '{"subject": "Thanks", "text": "Hi {name}, 50% off at {business}! {review_link}"}',   # price -> rejected
        "I cannot do that",                                                                   # no JSON -> rejected
        '{"subject": "Thanks", "text": "Hi {name}, thanks for choosing {business}. Review us: {review_link}"}',
        '{"subject": "Thanks", "text": "Hi {name}, thanks for choosing {business}. Review us: {review_link}"}',  # duplicate
        '{"subject": "Quick favour", "text": "Hi {name}, could you review {business}? {review_link}"}',
        '{"subject": "Thank you", "text": "{name}, thank you from {business}. A short review helps: {review_link}"}',
    ])
    seen = []

    def chat(msgs, temperature, seed):
        seen.append(seed)
        return next(outputs)

    res = write_templates(chat, "fake bike shop", "friendly", "review_request")
    assert len(res["templates"]) == 3 and seen == [0, 1, 2, 3, 4, 5]
    assert [a["accepted"] for a in res["attempts"]] == [False, False, True, False, True, True]
    assert res["attempts"][3]["problems"] == ["duplicate"]
    f = templates_file(res, "fake bike shop", "friendly", "review_request", "local_model:fake/model")
    assert f["attempts"] == 6 and f["rejected"] == 3
    assert run_js(f"console.log(JSON.stringify(Core.checkTemplatesFile({json.dumps(f)})))") == []


def test_gives_up_after_max_attempts():
    res = write_templates(lambda m, temperature, seed: "nope", "fake salon", "brief", "follow_up", max_attempts=4)
    assert res["templates"] == [] and len(res["attempts"]) == 4


def test_unknown_tone_rejected():
    with pytest.raises(ValueError):
        write_templates(lambda m, temperature, seed: "", "fake", "angry", "follow_up")


def test_page_refuses_bad_templates_file():
    bad = {"format": "draft-pack-templates", "version": 1, "template": "follow_up", "tone": "brief",
           "templates": [{"text": "Hi {name}, 10% off at {business} {date}", "subject": "Hi"}]}
    got = run_js(f"console.log(JSON.stringify(Core.checkTemplatesFile({json.dumps(bad)})))")
    assert got and all(x.startswith("suggestion 1") for x in got)
