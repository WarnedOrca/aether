"""Tests for tool/draft-pack.html: the page's pure logic (between CORE-START and CORE-END) runs in Node on made-up rows,
and static checks make sure the page cannot reach the network or send anything by itself."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "tool/draft-pack.html").read_text(encoding="utf-8")
CORE = PAGE.split("// CORE-START", 1)[1].split("// CORE-END", 1)[0]


def run_js(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "//" + CORE + "\n" + body
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


SAMPLE = (ROOT / "tool/SAMPLE-DATA.csv").read_text(encoding="utf-8")
CFG = {"map": {"name": "name", "phone": "phone", "email": "email", "date": "appointment_date", "opted_out": "opted_out",
               "last_contacted": "last_contacted"},
       "extra": {"business": "Test Business"}, "text": None, "subject": "Reminder", "channel": "sms",
       "date_mode": "ahead", "date_days": 1, "min_days_since_contact": 7, "daily_limit": 50, "window": ["09:00", "20:00"]}


def build(cfg_changes=None, today="2026-12-01"):
    cfg = dict(CFG, **(cfg_changes or {}))
    return run_js(f"""
const d = Core.parseCSV({json.dumps(SAMPLE)});
const cfg = {json.dumps(cfg)};
if (cfg.text === null) cfg.text = TEMPLATES.appointment_reminder.text;
console.log(JSON.stringify(Core.build(d.rows, cfg, {json.dumps(today)})));""")


def test_sample_file_drafts_and_skip_reasons():
    r = build()
    assert [d["name"] for d in r["drafts"]] == ["Fake Customer A", "Fake Customer I"]
    assert r["drafts"][0]["to"] == "+12145550101" and r["drafts"][1]["to"] == "+12145550109"
    assert r["drafts"][0]["text"].startswith("Hi Fake Customer A, this is a reminder from Test Business about your appointment on 2026-12-02.")
    reasons = {s["name"]: s["reason"] for s in r["skipped"]}
    assert reasons["Fake Customer B"] == "opted out"
    assert reasons["Fake Customer C"].startswith("phone number looks wrong")
    assert reasons["Fake Customer D"].startswith("contacted on 2026-11-28, less than 7 days ago")
    assert reasons["Fake Customer E"].startswith("not due today")
    assert reasons["Fake Customer F"] == "no phone number"
    assert reasons["Fake Customer G"].startswith("unclear opt-out value")  # never guessed
    assert reasons["Fake Customer H"].startswith("can't read date")
    assert reasons["Fake Customer J"].startswith("not due today")
    assert len(r["drafts"]) + len(r["skipped"]) == 10  # every row is accounted for


def test_daily_limit_and_rules():
    r = build({"daily_limit": 1})
    assert [d["name"] for d in r["drafts"]] == ["Fake Customer A"]
    assert any(s["reason"] == "over today's limit of 1" for s in r["skipped"])
    r = build({"min_days_since_contact": 0})  # D is no longer skipped for recent contact
    assert "Fake Customer D" in [d["name"] for d in r["drafts"]]
    r = build({"channel": "email"})
    reasons = {s["name"]: s["reason"] for s in r["skipped"]}
    assert "Fake Customer F" in [d["name"] for d in r["drafts"]]  # has an email
    assert reasons["Fake Customer H"].startswith("can't read date")


def test_missing_placeholder_is_flagged_not_guessed():
    r = build({"extra": {}})  # {business} has no value
    assert r["drafts"] == []
    assert all("missing value for {business}" in s["reason"] or not s["reason"].startswith("missing") for s in r["skipped"])
    assert any(s["reason"] == "missing value for {business}" for s in r["skipped"])


def test_helpers_and_config_checks():
    out = run_js("""console.log(JSON.stringify({
      p: [Core.phone("(214) 555-0101"), Core.phone("1-214-555-0101"), Core.phone("555-0101"), Core.phone("call me")],
      e: [Core.email("a@example.com"), Core.email("a@b"), Core.email("")],
      d: [Core.parseDate("2026-02-30"), Core.parseDate("2/3/2026"), Core.parseDate(""), Core.parseDate("soon")],
      o: [Core.optOut("YES"), Core.optOut(""), Core.optOut("perhaps")],
      w: [Core.inWindow("08:59","09:00","20:00"), Core.inWindow("09:00","09:00","20:00"), Core.inWindow("20:00","09:00","20:00"), Core.inWindow("23:00","22:00","06:00")],
      c: Core.checkConfig({daily_limit: 500, min_days_since_contact: 7, window: ["09:00","09:00"], channel: "sms", map: {name: "n", phone: "p"}, date_mode: "none"}),
      sms: Core.smsLink("+12145550101", "Hi & bye"), csv: Core.toCSV(["a","b"], [["x,y", 'q"z']]),
      pilot: Core.PILOT_COLUMNS, row: Core.pilotRow("2026-12-01", "AB", "reminders", "before", 12.34)}));""")
    assert out["p"] == ["+12145550101", "+12145550101", None, None]
    assert out["e"] == ["a@example.com", None, None]
    assert out["d"] == [None, "2026-02-03", "", None]
    assert out["o"] == [True, False, None]
    assert out["w"] == [False, True, False, True]
    assert "daily limit must be 1-200" in out["c"] and "sending hours must be two different times" in out["c"]
    assert "choose the column that says who opted out" in out["c"]
    assert out["sms"] == "sms:+12145550101?&body=Hi%20%26%20bye"
    assert out["csv"] == 'a,b\r\n"x,y","q""z"\r\n'
    header = (ROOT / "private/pilot-log.csv").read_text().splitlines()[0].split(",") if (ROOT / "private/pilot-log.csv").exists() else None
    if header:
        assert out["pilot"] == header  # the timing download matches the private log's columns
    assert out["row"][4] == "12.3" and out["row"][3] == "before" and len(out["row"]) == len(out["pilot"])


def test_page_cannot_reach_the_network_or_send():
    assert "default-src 'none'" in PAGE  # Content-Security-Policy blocks all network loads
    urls = re.findall(r"https?://", PAGE)
    assert urls == [], urls
    for banned in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "localStorage", "sessionStorage", "indexedDB", "<form", "import("):
        assert banned not in PAGE, banned
    assert "minutes saved" not in PAGE.lower() and "time saved" not in PAGE.lower().replace("estimates time saved", "")
    assert "Nothing is uploaded" in PAGE


def test_templates_in_page_match_the_job_spec_templates():
    spec = ROOT / "jobspec/templates.json"
    if not spec.exists():
        pytest.skip("job spec templates not created yet")
    embedded = json.loads(PAGE.split("/*TEMPLATES-START*/", 1)[1].split("/*TEMPLATES-END*/", 1)[0])
    assert embedded == json.loads(spec.read_text(encoding="utf-8"))


def test_page_parser_matches_python_baseline():
    """The page's one-sentence parser is a port of jobspec/baseline.py; both give the same spec on the dev split
    (never the held-out set) and on extra edge cases."""
    from jobspec.baseline import parse

    texts = [json.loads(line)["request"] for line in (ROOT / "eval/jobspec-dev/requests.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    texts += ["", "hello", "Send 900 reminders a day", "Remind people between 9 and 5", "at noon remind", "review between 7pm and 6pm",
              "Follow up, skip anyone from the last fortnight", "invoices once every 3 weeks by e-mail", "Remind at 3 in the morning"]
    got = run_js("console.log(JSON.stringify(" + json.dumps(texts) + ".map(Core.parseRequest)))")
    for text, js in zip(texts, got):
        assert js == parse(text), text


def test_ai_audit_detail_has_no_free_text():
    """Audit rows for AI suggestions hold only kind, id, a known field name, an outcome and the producer id."""
    got = run_js('console.log(JSON.stringify(['
                 'Core.aiAuditDetail("settings", 1, "daily_limit", "edited", "local_model:Qwen/Qwen2.5-7B-Instruct"),'
                 'Core.aiAuditDetail("template", 2, "Fake Customer A, 214-555-0100", "maybe", "keyword; DROP <x> @a b"),'
                 'Core.aiAuditDetail("x", "7", "text", "rejected", "")]))')
    assert got == ["kind=settings; id=1; field=daily_limit; outcome=edited; source=local_model:Qwen/Qwen2.5-7B-Instruct",
                   "kind=template; id=2; field=other; outcome=other; source=keywordDROPxab",
                   "kind=other; id=0; field=text; outcome=rejected; source=unknown"]
