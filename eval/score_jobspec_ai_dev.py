"""Scores the author-written AI dev check (CPU only). Development only: not an independent test.

    .venv/Scripts/python.exe -m eval.score_jobspec_ai_dev [--raw eval/results/jobspec-ai-dev/raw-interpret-v1.jsonl]

Systems (same per-item rules as docs/jobspec/DESIGN.md "Evaluation plan", via eval.jobspec_score.score):
  keyword            the keyword rules (jobspec/baseline.py)
  model              the local model's greedy answer only
  model+fallback     what jobspec.interpret ships: the model's answer if it validates, else the keyword rules
                     (only meaningful with validation)
Writer: share of generated wordings that passed the script checks, and whether each case reached 3 wordings.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from eval.compare import mcnemar_exact, wilson
from eval.jobspec_score import load, score
from jobspec.baseline import parse

REQUESTS = "eval/jobspec-ai-dev/requests.jsonl"


def strip(res: dict) -> dict:
    return {k: v for k, v in res.items() if k != "items"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="eval/results/jobspec-ai-dev/raw-interpret-v1.jsonl")
    ap.add_argument("--out")
    a = ap.parse_args()
    rows = load(REQUESTS)
    raw = load(a.raw)
    model = {r["id"]: r for r in raw if r["key"].startswith("interpret:")}
    missing = [r["id"] for r in rows if r["id"] not in model]
    if missing:
        raise SystemExit(f"{len(missing)} requests have no model answer yet; rerun eval.run_jobspec_ai_dev")
    kw = {r["id"]: json.dumps(parse(r["request"])) for r in rows}
    preds = {"keyword": {i: {"outputs": [kw[i]]} for i in kw},
             "model": {i: {"outputs": [model[i]["raw"]]} for i in kw},
             "model+fallback": {i: {"outputs": [model[i]["raw"], kw[i]]} for i in kw}}
    res = {}
    for name, p in preds.items():
        for v in (False, True):
            if name == "model+fallback" and not v:
                continue
            res[f"{name}|{'with' if v else 'without'}_validation"] = score(rows, p, v)
    a_items = res["model+fallback|with_validation"]["items"]
    b_items = res["keyword|with_validation"]["items"]
    only_a = sum(x["correct"] and not y["correct"] for x, y in zip(a_items, b_items))
    only_b = sum(y["correct"] and not x["correct"] for x, y in zip(a_items, b_items))
    fallback_used = sum(1 for r in rows if _validates_first(model[r["id"]]["raw"]) is False)
    writers = [r for r in raw if r["key"].startswith("writer:")]
    att = [x for w in writers for x in w["attempts"]]
    reasons = Counter(p.split(":")[0] for x in att for p in x["problems"])
    writer = {"cases": len(writers), "attempts": len(att), "accepted": sum(x["accepted"] for x in att),
              "pass_rate_wilson95": [round(v, 4) for v in wilson(sum(x["accepted"] for x in att), len(att))] if att else None,
              "first_attempt_accepted": sum(w["attempts"][0]["accepted"] for w in writers if w["attempts"]),
              "cases_reaching_3": sum(len(w["templates"]) >= 3 for w in writers),
              "rejection_reasons": dict(reasons),
              "per_case": [{"case": w["case"], "kept": len(w["templates"]), "attempts": len(w["attempts"])} for w in writers]}
    out = {"label": "author-written, development only, not an independent test", "requests": REQUESTS, "raw": a.raw,
           "n": len(rows), "model": raw[0]["model"], "revision": raw[0]["revision"],
           "prompt_version": model[rows[0]["id"]]["prompt_version"],
           "systems": {k: strip(v) for k, v in res.items()},
           "model+fallback_vs_keyword_with_validation": {"only_model+fallback_correct": only_a, "only_keyword_correct": only_b,
                                                         "mcnemar_exact_p": round(mcnemar_exact(only_a, only_b), 4),
                                                         "note": "descriptive; author-written dev set; not a confirmatory test"},
           "model_answers_that_failed_validation_so_fallback_used": fallback_used,
           "writer": writer,
           "items": {k: v["items"] for k, v in res.items()}}
    path = Path(a.out or Path(a.raw).with_name(Path(a.raw).stem.replace("raw-", "summary-") + ".json"))
    path.write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")
    for k, v in res.items():
        print(f"{k:38s} {v['correct']}/{v['n']} {v['wilson95']} {v['by_category']} invalid {v['invalid']}")
    print("model+fallback vs keyword:", out["model+fallback_vs_keyword_with_validation"])
    print("fallback used:", fallback_used)
    print("writer:", {k: v for k, v in writer.items() if k != "per_case"})
    print("wrote", path)


def _validates_first(raw: str):
    from eval.jobspec_score import validate
    return validate(raw) is not None


if __name__ == "__main__":
    main()
