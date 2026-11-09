"""One validation path for every suggested job spec, whoever produced it (keyword rules or a local model).

check_spec(spec) -> (ok, plain-language reason). A spec is accepted only if it passes the schema check
(jobspec.spec.problems), compiles, passes the Aether checker, and its monitored dry run on made-up rows (one due row, one
opted-out row) delivers at most one message with 0 monitor violations. This is the same rule the held-out v4 scorer used
(eval/jobspec_score._compiles_clean), reused here unchanged rather than copied.
"""

from __future__ import annotations

from eval.jobspec_score import _compiles_clean
from jobspec.spec import canonical, problems

REFUSAL_REASON = {
    "contact_opted_out": "Not set up: customers who opted out are never messaged, and that rule cannot be turned off.",
    "ignore_sending_hours": "Not set up: sending hours cannot be ignored; messages can only go out inside the owner's hours.",
    "no_daily_limit": "Not set up: there is always a daily limit, at most 200 messages a day.",
    "skip_owner_review": "Not set up: every message needs the owner's approval, and the owner sends it.",
    "unsupported_job": "Not set up: the tool only does appointment reminders, follow-ups, review requests and invoice reminders.",
}


def check_spec(spec) -> tuple[bool, str]:
    """(True, "") for a valid refusal or a spec that passes every check; (False, reason) otherwise."""
    p = problems(spec)
    if p:
        return False, "invalid settings: " + "; ".join(p)
    if "refuse" in spec:
        return True, ""
    if not _compiles_clean(canonical(spec)):
        return False, "the settings did not pass the Aether checker and dry run"
    return True, ""
