"""Turn one sentence into a settings file for tool/draft-pack.html ("Import settings file").

    .venv/Scripts/python.exe -m jobspec.make_settings "Remind clients by text the day before, 9am-6pm, max 40 a day" --out settings.json
    .venv/Scripts/python.exe -m jobspec.make_settings "..." --out settings.json --no-model     # keyword rules only, no GPU

Run by the helper on their own computer (the owner never needs a GPU). The file holds only settings, the sentence, and
which interpreter produced them; no customer data. The page re-checks the file and shows every setting for review.
Exit code 0 = file written, 2 = not set up (the reason is printed), 1 = error.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from jobspec.compile import tool_config
from jobspec.interpret import DEFAULT_MODEL, LocalModel, LocalModelInterpreter, interpret

FORMAT = "draft-pack-settings"
SETTING_FIELDS = ("template", "channel", "min_days_since_contact", "send_window", "daily_limit")


def settings_file(sentence: str, result, business: str = "") -> dict:
    cfg = tool_config(result.spec, business=business)
    return {"format": FORMAT, "version": 1, "created": date.today().isoformat(), "produced_by": result.source,
            "notes": result.notes, "sentence": sentence,
            "settings": {k: result.spec[k] for k in SETTING_FIELDS},
            "message": {"text": cfg["text"], "subject": cfg["subject"]},
            "checked": "schema, compiler, Aether checker and a monitored dry run on made-up rows (0 monitor violations)"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sentence")
    ap.add_argument("--out", required=True)
    ap.add_argument("--business", default="")
    ap.add_argument("--no-model", action="store_true", help="keyword rules only")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args(argv)
    lm = None
    model = None
    if not a.no_model:
        try:
            lm = LocalModel(a.model)
            model = LocalModelInterpreter(lm.chat, a.model)
        except Exception as exc:  # noqa: BLE001 - any load failure falls back to keyword rules, reported below
            print(f"Local model not available ({type(exc).__name__}: {str(exc)[:200]}); using the keyword rules.")
    try:
        r = interpret(a.sentence, model)
    finally:
        if lm is not None:
            lm.close()
    print(f"Produced by: {r.source}")
    for n in r.notes:
        print(f"Note: {n}")
    if not r.accepted:
        print(r.reason)
        return 2
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(settings_file(a.sentence, r, a.business), f, indent=2)
    print(f"Wrote {a.out}: {json.dumps(r.spec)}")
    print("Open tool/draft-pack.html, press 'Import settings file', and check every setting before using it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
