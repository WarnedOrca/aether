"""Author-written dev check of the AI setup helper and message writer (GPU, resumable).

    .venv/Scripts/python.exe -u -m eval.run_jobspec_ai_dev --out eval/results/jobspec-ai-dev/raw-interpret-v1.jsonl
    .venv/Scripts/python.exe -m eval.score_jobspec_ai_dev                          # CPU scoring -> summary json

Loads the local model once (GPU guard), then for every request in eval/jobspec-ai-dev/requests.jsonl stores the model's
raw greedy answer, and for each writer case the full attempt record. One JSON line per finished item; rerunning skips
finished items, so a crash or shutdown loses at most one item. Development only (author-written sentences).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from jobspec.interpret import DEFAULT_MODEL, LocalModel, build_messages
from jobspec.writer import PROMPT_VERSION as WRITER_VERSION
from jobspec.writer import write_templates

REQUESTS = "eval/jobspec-ai-dev/requests.jsonl"
# 12 writer cases: every job x tone once, spread over business types from the dev set.
WRITER_CASES = [("dentist", "friendly", "appointment_reminder"), ("auto repair shop", "formal", "appointment_reminder"),
                ("pet groomer", "brief", "appointment_reminder"), ("hair salon", "friendly", "follow_up"),
                ("physical therapy clinic", "formal", "follow_up"), ("dog trainer", "brief", "follow_up"),
                ("bakery", "friendly", "review_request"), ("photographer", "formal", "review_request"),
                ("nail salon", "brief", "review_request"), ("plumber", "friendly", "invoice_nudge"),
                ("tax preparer", "formal", "invoice_nudge"), ("landscaper", "brief", "invoice_nudge")]


def done_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(line)["key"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--prompt-version", default="interpret-v1")
    ap.add_argument("--skip-writer", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = done_keys(out)
    rows = [json.loads(line) for line in open(REQUESTS, encoding="utf-8") if line.strip()]
    todo = [r for r in rows if f"interpret:{r['id']}" not in done]
    wtodo = [] if a.skip_writer else [c for c in WRITER_CASES if f"writer:{'|'.join(c)}" not in done]
    print(f"{len(done)} items done; {len(todo)} requests and {len(wtodo)} writer cases to go", flush=True)
    if not todo and not wtodo:
        return
    lm = LocalModel(a.model)
    try:
        with open(out, "a", encoding="utf-8", newline="\n") as f:
            for i, r in enumerate(todo, 1):
                t = time.time()
                raw = lm.chat(build_messages(r["request"], a.prompt_version))
                f.write(json.dumps({"key": f"interpret:{r['id']}", "id": r["id"], "raw": raw, "model": a.model,
                                    "revision": lm.revision, "prompt_version": a.prompt_version,
                                    "seconds": round(time.time() - t, 2)}) + "\n")
                f.flush()
                if i % 10 == 0:
                    print(f"interpret {i}/{len(todo)}", flush=True)
            for c in wtodo:
                t = time.time()
                res = write_templates(lm.chat, *c)
                f.write(json.dumps({"key": f"writer:{'|'.join(c)}", "case": c, **res, "model": a.model,
                                    "revision": lm.revision, "prompt_version": WRITER_VERSION,
                                    "seconds": round(time.time() - t, 2)}) + "\n")
                f.flush()
                print(f"writer {'|'.join(c)}: {len(res['templates'])} kept in {len(res['attempts'])} attempts", flush=True)
    finally:
        lm.close()
    print("finished", flush=True)


if __name__ == "__main__":
    main()
