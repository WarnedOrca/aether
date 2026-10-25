"""Run the property suite (P1-P9) and checker mutation testing at scale; save real counts.

Usage:  uv run python eval/run_properties.py [--seeds 100]
Writes: eval/results/properties-<date>.json  (numbers for METRICS.md come only from here)
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checker.mutate import run_mutants  # noqa: E402
from interpreter import props  # noqa: E402


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    args = ap.parse_args()
    started = time.time()
    viol: Counter = Counter()
    examples: list[dict] = []
    n_cases = 0
    for name in sorted(props.EXAMPLES.procedures):
        for behavior in props.BEHAVIORS:
            for empty in (0.0, 0.1, 0.3):
                for seed in range(args.seeds):
                    n_cases += 1
                    for p in props.run_case(name, seed, behavior, empty):
                        viol[p.split()[0]] += 1
                        if len(examples) < 20:
                            examples.append({"case": [name, seed, behavior, empty], "problem": p})
    n_p5 = 0
    for kind in props.TAMPER:
        for seed in range(args.seeds):
            n_p5 += 1
            for p in props.batch_tamper_case(seed, kind):
                viol[p.split()[0]] += 1
                examples.append({"case": ["P5", seed, kind], "problem": p})
    n_p6 = args.seeds * 5
    for seed in range(n_p6):
        for p in props.policy_case(seed):
            viol[p.split()[0]] += 1
            examples.append({"case": ["P6", seed], "problem": p})
    mut = run_mutants()
    result = {
        "date": date.today().isoformat(),
        "commit": _git_commit(),
        "python": platform.python_version(),
        "seconds": round(time.time() - started, 1),
        "cases": {"P1-P4,P7,P8,P9 (examples x behaviors x blank rates x seeds)": n_cases,
                  "P5 batch tamper": n_p5, "P6 random policies": n_p6},
        "violations": dict(viol),
        "violation_examples": examples[:20],
        "mutants": {"total": len(mut), "rejected": sum(r["rejected"] for r in mut),
                    "rejected_with_expected_code": sum(r["expected_found"] for r in mut),
                    "by_operator": dict(Counter(r["operator"] for r in mut))},
    }
    out_dir = ROOT / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"properties-{result['date']}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    total = n_cases + n_p5 + n_p6
    print(f"cases={total} violations={sum(viol.values())} mutants={len(mut)} "
          f"expected_code={result['mutants']['rejected_with_expected_code']} -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
