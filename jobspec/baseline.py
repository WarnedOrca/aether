"""Keyword/regex baseline: plain-English request -> job spec JSON, no model.

    python -m jobspec.baseline "Text patients the day before, max 40 a day"

Written and debugged on the dev split only (eval/jobspec-dev). Anything it cannot read falls back to the documented
defaults, so an owner always gets a form pre-filled with something they can correct.
"""

from __future__ import annotations

import json
import re
import sys

from jobspec.spec import MAX_DAILY_LIMIT, default_spec

WORDNUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
           "nine": 9, "ten": 10, "couple of": 2, "few": 3}
UNIT = {"day": 1, "week": 7, "fortnight": 14, "month": 30}

OPT_OUT = r"opted[- ]out|opted out|unsubscrib|do[- ]not[- ]contact|not to contact|asked us to stop|blocked|stop texting"
SKIP_REVIEW = (r"without me (checking|looking|approving)|(don't|do not|no) need (to )?(approve|to show)|need to approve|"
               r"don't want to approve|no approval|skip (my |the )?(approval|review)|on their own|send themselves|"
               r"automatically|make me approve|without (my )?approval")
NO_LIMIT = r"no (daily )?limit|unlimited|no cap|as many|blast|whole list|entire customer list|as it takes"
ANY_TIME = r"(ignore|forget)( the)?( usual)? sending hours|any time of day|around the clock|no quiet hours|night or day|day or night"
UNSUPPORTED = (r"\bcall\b|voicemail|instagram|facebook|\bpost\b|charge|card|reply to|answer|order|refund|calendar|"
               r"book new|grades|scores|medical")


def _time(tok: str, pm_hint: bool = False) -> int | None:
    """'9am', '7:30pm', '19:00', 'noon', '9' -> minutes after midnight."""
    tok = tok.strip().lower().replace(".", "")
    if tok == "noon":
        return 12 * 60
    if tok == "midnight":
        return 0
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", tok)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if ap is None and pm_hint and h < 12:
        h += 12
    return h * 60 + mi if h < 24 and mi < 60 else None


def _hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


TIME = r"(noon|midnight|\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"


def _window(t: str):
    m = (re.search(rf"(?:between|from) {TIME} (?:and|to|-) {TIME}", t)
         or re.search(rf"(?:no \w+|nothing) before {TIME} or after {TIME}", t))
    if not m:
        return None
    a, b = _time(m.group(1)), _time(m.group(2))
    if a is None or b is None:
        return None
    if b <= a and "am" not in m.group(2) and b < 12 * 60:  # "between 9 and 5" -> 17:00
        b += 12 * 60
    return [_hhmm(a), _hhmm(b)] if a < b else None


def _single_odd_time(t: str) -> bool:
    """'at 6am', 'at 11pm', 'at midnight', 'at 3 in the morning': one send time outside normal hours."""
    for m in re.finditer(rf"\bat {TIME}( in the morning)?", t):
        v = _time(m.group(1))
        if v is not None and (m.group(2) or v < 7 * 60 or v >= 21 * 60 or m.group(1) == "midnight"):
            return True
    return False


def _num(s: str) -> int | None:
    s = s.strip()
    return int(s) if s.isdigit() else WORDNUM.get(s)


def _min_days(t: str):
    m = re.search(r"(?:last|past|within|in the last)\s+(?:the\s+)?(?:last\s+|past\s+)?(?:roughly the last\s+)?"
                  r"(\d+|a|an|one|two|three|four|five|six|couple of|few)?\s*(day|week|fortnight|month)s?", t)
    if not m:
        m = re.search(r"once (?:every|per|a|each) (\d+|two|three)?\s*(day|week|fortnight|month)s?", t)
    if not m:
        return None
    n = _num(m.group(1)) if m.group(1) else 1
    return n * UNIT[m.group(2)] if n else None


def _limit(t: str):
    pats = [r"(?:max(?:imum)?(?: of)?|at most|up to|no more than|cap(?:ped)?(?: it)? at|limit(?: it to)?|keep it to"
            r"|about|say) (\d+)",
            r"(\d+) (?:[a-z-]+ )?(?:a|per) day", r"(\d+) (?:max|tops|daily)", r"(\d+) per day"]
    for p in pats:
        m = re.search(p, t)
        if m:
            return int(m.group(1))
    return None


def _template(t: str):
    if re.search(r"invoice|unpaid|overdue|past[- ]due|owe|haven't paid|payment|money", t):
        return "invoice_nudge"
    if re.search(r"review", t):
        return "review_request"
    if re.search(r"remind|reminder", t):
        return "appointment_reminder"
    if re.search(r"follow[- ]?up|thank|check in|check on|how it went|how .* doing|after (each|a|their)", t):
        return "follow_up"
    return None


def parse(request: str) -> dict:
    t = " " + request.lower().replace("’", "'") + " "
    if re.search(OPT_OUT, t):
        return {"refuse": "contact_opted_out"}
    if re.search(NO_LIMIT, t):
        return {"refuse": "no_daily_limit"}
    big = _limit(t)
    if big is not None and big > MAX_DAILY_LIMIT:
        return {"refuse": "no_daily_limit"}
    if re.search(SKIP_REVIEW, t):
        return {"refuse": "skip_owner_review"}
    if re.search(ANY_TIME, t) or _single_odd_time(t):
        return {"refuse": "ignore_sending_hours"}
    template = _template(t)
    if template is None or (re.search(UNSUPPORTED, t) and not re.search(r"remind|review|invoice|follow", t)):
        return {"refuse": "unsupported_job"}
    spec = default_spec(template)
    ch = re.search(r"\b(e-?mail|text|sms)", t)
    if ch:
        spec["channel"] = "email" if ch.group(1).startswith("e") else "sms"
    d = _min_days(t)
    if d is not None and 0 <= d <= 365:
        spec["min_days_since_contact"] = d
    w = _window(t)
    if w:
        spec["send_window"] = w
    n = _limit(t)
    if n is not None and 1 <= n <= MAX_DAILY_LIMIT:
        spec["daily_limit"] = n
    return spec


if __name__ == "__main__":
    print(json.dumps(parse(" ".join(sys.argv[1:]))))
