"""AI message writer: a local open-weight model drafts message wordings; a script checks every one.

    .venv/Scripts/python.exe -m jobspec.writer --business-type "bike repair shop" --tone friendly --job review_request --out templates.json

The owner (in tool/draft-pack.html, "Import message suggestions") picks one wording, edits it, or uses none. Nothing is
sent by the tool. check_template() is the same rule set as Core.checkTemplate in the page (tests/test_writer.py checks
they agree): every required {placeholder} present, no other placeholders, no numbers, no prices/discounts/offers, no links
or addresses, no medical/legal/guarantee claims, at most MAX_CHARS characters. A rejected wording is regenerated (new seed)
up to a fixed number of attempts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from typing import Callable

from jobspec.spec import TEMPLATES, parse_output

REQUIRED = {"appointment_reminder": ["name", "business", "date"], "follow_up": ["name", "business", "date"],
            "review_request": ["name", "business", "review_link"], "invoice_nudge": ["name", "invoice", "amount", "date"]}
ALLOWED = {"name", "business", "date", "review_link", "invoice", "amount"}
TONES = ("friendly", "formal", "brief")
MAX_CHARS = 320
PROMPT_VERSION = "writer-v1"

_PRICE = re.compile(r"[$€£¥%]|\b(usd|dollars?|cents?|price|prices|cost|costs|fee|fees|discount\w*|coupon\w*|promo\w*|deal|deals|"
                    r"sale|sales|cheap\w*|offer\w*|bogo|rebate\w*)\b|\bfor free\b|\bfree of charge\b|"
                    r"\bfree (gift|service|session|consultation|trial|month|week)\b", re.I)
_LINK = re.compile(r"https?:|www\.|\.(com|net|org|io|co|us|biz|info)\b|@", re.I)
_CLAIM = re.compile(r"\b(cure|cures|heal|heals|healing|treat|treats|treatment|diagnos\w*|prescri\w*|medical|medicine|symptoms?|"
                    r"guarantee\w*|warrant\w*|legal|lawsuit|liab\w*|attorney|lawyer|insurance|risk-free|safe|proven|clinically)\b", re.I)


def check_template(text, template: str) -> list[str]:
    """Problems with one wording (empty list = acceptable). Mirrors Core.checkTemplate in tool/draft-pack.html."""
    req = REQUIRED.get(template, [])
    if not isinstance(text, str) or not text.strip():
        return ["empty"]
    used = re.findall(r"\{([^{}]*)\}", text)
    p = []
    missing = [r for r in req if r not in used]
    unknown = list(dict.fromkeys(u for u in used if u not in ALLOWED or u not in req))
    if missing:
        p.append("missing placeholders: " + ", ".join(missing))
    if unknown:
        p.append("placeholders not allowed for this job: " + ", ".join(unknown))
    bare = re.sub(r"\{[^{}]*\}", "", text)
    if re.search(r"[{}]", bare):
        p.append("stray brace")
    if len(text) > MAX_CHARS:
        p.append(f"longer than {MAX_CHARS} characters")
    if re.search(r"\d", bare):
        p.append("contains a number (prices, times or amounts must come from your list, not the wording)")
    if _PRICE.search(bare):
        p.append("mentions a price, discount or offer")
    if _LINK.search(bare):
        p.append("contains a link or address")
    if _CLAIM.search(bare):
        p.append("makes a medical, legal or guarantee claim")
    return p


def check_subject(subject) -> list[str]:
    if not isinstance(subject, str) or len(subject) > 80 or re.search(r"[{}\d]", subject):
        return ["subject must be short, with no numbers or placeholders"]
    return []


def messages_for(business_type: str, tone: str, job: str, avoid: list[str]) -> list[dict]:
    t = TEMPLATES[job]
    req = ", ".join("{" + r + "}" for r in REQUIRED[job])
    tone_rule = {"friendly": "warm and friendly", "formal": "polite and formal", "brief": "as short as possible"}[tone]
    avoid_txt = ("\nWrite something different from these:\n" + "\n".join(f"- {a}" for a in avoid)) if avoid else ""
    return [{"role": "system", "content":
             "You write one short customer message template for a small business. Answer with ONE JSON object: "
             '{"subject": "...", "text": "..."} and nothing else.\n'
             f"Rules: use exactly these placeholders, each at least once: {req}. Use no other placeholders and no "
             "other curly braces. No numbers, prices, discounts, offers, links, email addresses, or medical, legal "
             f"or guarantee claims. At most {MAX_CHARS - 40} characters. Subject: at most 6 words, no numbers."},
            {"role": "user", "content": f"Business type: {business_type}. Job: {t['label']}. Tone: {tone_rule}.\n"
                                        f"Example of the job (do not copy): {t['text']}{avoid_txt}"}]


def write_templates(chat: Callable[..., str], business_type: str, tone: str, job: str, n: int = 3,
                    max_attempts: int = 12) -> dict:
    """chat(messages, temperature=..., seed=...) -> text. Returns {"templates": [...], "attempts": [...]}."""
    if tone not in TONES or job not in TEMPLATES:
        raise ValueError("unknown tone or job")
    kept, attempts = [], []
    for k in range(max_attempts):
        if len(kept) >= n:
            break
        raw = chat(messages_for(business_type, tone, job, [m["text"] for m in kept]), temperature=0.8, seed=k)
        obj = parse_output(raw)
        if not isinstance(obj, dict):
            problems = ["no JSON object"]
        else:
            problems = check_template(obj.get("text"), job) + check_subject(obj.get("subject", ""))
            if not problems and any(obj["text"].strip() == m["text"] for m in kept):
                problems = ["duplicate"]
        attempts.append({"attempt": k, "accepted": not problems, "problems": problems})
        if not problems:
            kept.append({"text": obj["text"].strip(), "subject": obj.get("subject", "").strip()})
    return {"templates": kept, "attempts": attempts}


def templates_file(result: dict, business_type: str, tone: str, job: str, source: str) -> dict:
    return {"format": "draft-pack-templates", "version": 1, "created": date.today().isoformat(), "produced_by": source,
            "prompt_version": PROMPT_VERSION, "business_type": business_type, "tone": tone, "template": job,
            "templates": result["templates"],
            "attempts": len(result["attempts"]), "rejected": sum(not a["accepted"] for a in result["attempts"])}


def main(argv=None) -> int:
    from jobspec.interpret import DEFAULT_MODEL, LocalModel

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--business-type", required=True)
    ap.add_argument("--tone", choices=TONES, default="friendly")
    ap.add_argument("--job", choices=list(TEMPLATES), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args(argv)
    try:
        lm = LocalModel(a.model)
    except Exception as exc:  # noqa: BLE001
        print(f"Local model not available ({type(exc).__name__}: {str(exc)[:200]}). Keep the built-in wording; no file written.")
        return 1
    try:
        res = write_templates(lm.chat, a.business_type, a.tone, a.job)
    finally:
        lm.close()
    for at in res["attempts"]:
        print(f"attempt {at['attempt']}: {'kept' if at['accepted'] else 'rejected: ' + '; '.join(at['problems'])}")
    if not res["templates"]:
        print("No wording passed the checks; keep the built-in wording. No file written.")
        return 2
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(templates_file(res, a.business_type, a.tone, a.job, f"local_model:{a.model}"), f, indent=2)
    print(f"Wrote {a.out} with {len(res['templates'])} wordings. Open the page and press 'Import message suggestions'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
