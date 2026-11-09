"""scripts/pilot_report.py on the made-up files in scripts/sample/ (numbers checked by hand)."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pilot_report import report  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REP = report(ROOT / "scripts/sample/pilot-log.csv", ROOT / "scripts/sample/logs")


def test_counts_and_reasons():
    a = REP["businesses"]["FAKE-A"]
    assert a["counts"] == {"drafted": 5, "approved": 4, "skipped_by_owner": 1, "sent": 3}  # one approval was undone
    assert a["skips"]["duplicate"] == 1 and a["skips"]["opted out"] == 1 and a["skips"]["bad contact"] == 1
    assert a["skips"]["outside sending hours (held until the owner's hours)"] == 1
    assert REP["businesses"]["FAKE-B"]["skips"]["bad contact"] == 1  # missing contact counts as bad contact


def test_hours_use_timed_runs_only():
    t = REP["businesses"]["FAKE-A"]["timing"]["reminder texts"]
    # before: 40 (owner timed) and 38 (stopwatch) -> 39; after: 12 and 10 -> 11
    assert (t["mean_timed_minutes_before"], t["mean_timed_minutes_after"], t["percent_change"]) == (39.0, 11.0, -71.8)
    assert t["hours_saved_per_month"] == round(28 * 5 * 52 / 12 / 60, 2)
    b = REP["businesses"]["FAKE-B"]["timing"]["invoice reminders"]
    assert "hours_saved_per_month" not in b and b["estimates_not_used"] == 1  # an estimate is never used


def test_four_weeks_and_totals():
    t = REP["total"]
    assert t["businesses_with_any_data"] == 2 and t["businesses_with_at_least_4_weeks"] == 1
    assert (t["drafted"], t["approved"], t["sent"]) == (6, 5, 3)


def test_revenue_only_confirmed_counts():
    t = REP["total"]
    assert t["owner_reported_revenue_confirmed_usd"] == [(270.0, "4 weeks")]
    assert t["owner_reported_revenue_unconfirmed_count"] == 1


def test_ai_rates():
    assert REP["total"]["ai"] == {"settings": {"accepted_unchanged": 2, "edited": 1}, "template": {"edited": 1, "rejected": 1}}


def test_cli_prints_labels_and_no_data(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "scripts/pilot_report.py"), "--pilot-log", str(ROOT / "scripts/sample/pilot-log.csv"),
                          "--logs", str(ROOT / "scripts/sample/logs")], capture_output=True, text=True, check=True).stdout
    assert "OWNER-REPORTED, NOT MEASURED BY THE TOOL" in out and "NOT confirmed in writing: do not use anywhere" in out
    assert "owners report $270 over 4 weeks" in out and "no data" in out
    empty = subprocess.run([sys.executable, str(ROOT / "scripts/pilot_report.py"), "--pilot-log", str(tmp_path / "none.csv"),
                            "--logs", str(tmp_path)], capture_output=True, text=True, check=True).stdout
    assert "Businesses with any data: 0" in empty and "Hours saved per month (timed runs only): no data" in empty


def test_sample_files_are_marked_made_up():
    assert "NOT real data" in (ROOT / "scripts/sample/README.md").read_text(encoding="utf-8")
    assert all("MADE-UP SAMPLE" in line for line in (ROOT / "scripts/sample/pilot-log.csv").read_text(encoding="utf-8").splitlines()[1:])


def test_sample_header_matches_page_and_private_log():
    import json
    import re
    page = (ROOT / "tool/draft-pack.html").read_text(encoding="utf-8")
    cols = json.loads(re.search(r"PILOT_COLUMNS: (\[.*?\])", page).group(1))
    assert (ROOT / "scripts/sample/pilot-log.csv").read_text(encoding="utf-8").splitlines()[0].split(",") == cols
