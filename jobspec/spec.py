"""The job spec: a small JSON object that says which tested message job to run and with which rules.

A request is turned into exactly one of:
  {"template": T, "channel": "sms"|"email", "min_days_since_contact": int, "send_window": ["HH:MM", "HH:MM"], "daily_limit": int}
  {"refuse": REASON}
Opt-out skipping is not a field: it is always on and cannot be switched off. See docs/jobspec/DESIGN.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

TEMPLATES = json.loads((Path(__file__).with_name("templates.json")).read_text(encoding="utf-8"))
TEMPLATE_NAMES = tuple(TEMPLATES)
CHANNELS = ("sms", "email")
REFUSALS = ("contact_opted_out", "ignore_sending_hours", "no_daily_limit", "skip_owner_review", "unsupported_job")
MAX_DAILY_LIMIT = 200
DEFAULT_WINDOW = ("09:00", "20:00")
DEFAULT_LIMIT = 50
DEFAULT_MIN_DAYS = {"appointment_reminder": 0, "follow_up": 7, "review_request": 30, "invoice_nudge": 7}
FIELDS = ("template", "channel", "min_days_since_contact", "send_window", "daily_limit")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def default_spec(template: str) -> dict:
    """The spec a request gets when it names only the job: every rule at its documented default."""
    return {"template": template, "channel": TEMPLATES[template]["channel"], "min_days_since_contact": DEFAULT_MIN_DAYS[template],
            "send_window": list(DEFAULT_WINDOW), "daily_limit": DEFAULT_LIMIT}


def problems(spec) -> list[str]:
    """Empty list if the spec is valid. A refusal is valid if its reason is known."""
    if not isinstance(spec, dict):
        return ["not a JSON object"]
    if "refuse" in spec:
        return [] if set(spec) == {"refuse"} and spec["refuse"] in REFUSALS else ["unknown refusal or extra fields"]
    p = []
    if set(spec) != set(FIELDS):
        p.append(f"fields must be exactly {list(FIELDS)}")
    if spec.get("template") not in TEMPLATE_NAMES:
        p.append("unknown template")
    if spec.get("channel") not in CHANNELS:
        p.append("channel must be sms or email")
    d = spec.get("min_days_since_contact")
    if not (isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 365):
        p.append("min_days_since_contact must be an integer 0-365")
    w = spec.get("send_window")
    if not (isinstance(w, list) and len(w) == 2 and all(isinstance(x, str) and _HHMM.match(x) for x in w) and w[0] < w[1]):
        p.append("send_window must be [start, end] in HH:MM with start before end (sending overnight is not allowed)")
    n = spec.get("daily_limit")
    if not (isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= MAX_DAILY_LIMIT):
        p.append(f"daily_limit must be an integer 1-{MAX_DAILY_LIMIT}")
    return p


def canonical(spec) -> str:
    """One string per spec, for exact-match scoring."""
    return json.dumps(spec, sort_keys=True, separators=(",", ":"))


def parse_output(text: str):
    """The first JSON object in a model or baseline output, or None if there is none."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None
