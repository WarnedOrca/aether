"""EXPLORATORY, POST-HOC paired tests on the saved held-out v3 (stage 5) outputs. No model is run.

These two comparisons were NOT declared before the held-out v3 run (the only declared confirmatory comparison needed a
stage-4 model, which was not run). They were chosen after seeing the results, so they are descriptive only: no
multiple-comparison adjustment is applied and no claim is made from them jointly or singly.
  1. base1.5b-fewshot vs v0.2-plain                 (both plain runs, same 72 tasks)
  2. v0.2-plain vs v0.2-repaired (checker feedback) (the repair run's own round-0 rows are checked against v0.2-plain)

Usage: python -m eval.stage5_posthoc  ->  eval/results/stage5-posthoc.json
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.compare import mcnemar_exact, wilson
from stages.common import ROOT, write_json

RESULTS = ROOT / "eval/results"


def load(path: Path, which: str | None = None) -> dict[str, bool]:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["id"]: bool((r[which] if which else r)["safe_and_correct"]) for r in rows}


def paired(a_name: str, a: dict[str, bool], b_name: str, b: dict[str, bool]) -> dict:
    if set(a) != set(b):
        raise ValueError(f"{a_name} and {b_name} cover different tasks")
    a_only = sum(a[i] and not b[i] for i in a)
    b_only = sum(b[i] and not a[i] for i in a)
    n = len(a)
    return {"a": a_name, "b": b_name, "n": n,
            "a_correct": sum(a.values()), "a_ci95": wilson(sum(a.values()), n),
            "b_correct": sum(b.values()), "b_ci95": wilson(sum(b.values()), n),
            "a_only_correct": a_only, "b_only_correct": b_only,
            "mcnemar_exact_p": mcnemar_exact(a_only, b_only)}


def main() -> None:
    summary = json.loads((RESULTS / "stage5/summary.json").read_text(encoding="utf-8"))
    files = {k: RESULTS / v["file"] for k, v in summary["conditions"].items()}
    base = load(files["base1.5b-fewshot"])
    plain = load(files["v0.2-plain"])
    rep_plain = load(files["v0.2-repaired"], "plain")
    repaired = load(files["v0.2-repaired"], "repaired")
    if rep_plain != plain:
        raise ValueError("the repair run's round-0 rows do not match the v0.2-plain run")
    out = {
        "status": "EXPLORATORY, POST-HOC: not declared before the held-out v3 run; chosen after seeing results. "
                  "No multiple-comparison adjustment and no claim is made from these p-values.",
        "tasks": summary["tasks"], "conditions_sha256": summary["conditions_sha256"],
        "files": {k: v.name for k, v in files.items()},
        "test": "exact two-sided McNemar on safe_and_correct, all 72 tasks (eval.compare.mcnemar_exact)",
        "comparisons": [paired("base1.5b-fewshot", base, "v0.2-plain", plain),
                        paired("v0.2-plain", plain, "v0.2-repaired", repaired)],
    }
    write_json(RESULTS / "stage5-posthoc.json", out)
    for c in out["comparisons"]:
        print(f"{c['a']} {c['a_correct']}/{c['n']} vs {c['b']} {c['b_correct']}/{c['n']}: "
              f"a-only {c['a_only_correct']}, b-only {c['b_only_correct']}, exact McNemar p = {c['mcnemar_exact_p']:.4g}")


if __name__ == "__main__":
    main()
