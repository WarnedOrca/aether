"""Measure SOP overlap between a task folder and all training data and earlier evaluation sets.

Usage: uv run python -m eval.overlap_check eval/heldout2 [--out file.json]
Same measures as data/generate_traps.py: whole-SOP char-5-gram Jaccard, best difflib
sentence ratio, shared word 8-grams.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data.generate_traps import OverlapChecker

from .bench import load_tasks

ROOT = Path(__file__).resolve().parent.parent


def reference_sops(exclude: Path) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for name in ("synthetic", "synthetic_traps"):
        for split in ("train", "valid", "test"):
            f = ROOT / "data" / name / f"{split}.jsonl"
            if f.exists():
                groups.setdefault(name, []).extend(json.loads(line)["sop"] for line in f.open(encoding="utf-8"))
    groups["benchmark_110"] = [t.sop for t in load_tasks()]
    groups["heldout_v1_30"] = [t.sop for t in load_tasks(ROOT / "eval/heldout")]
    return {k: v for k, v in groups.items() if v}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out")
    args = ap.parse_args()
    tasks = load_tasks(ROOT / args.folder)
    report = {"folder": args.folder, "tasks": len(tasks), "against": {}}
    for name, sops in reference_sops(ROOT / args.folder).items():
        checker = OverlapChecker(sops)
        stats = [checker.check(t.sop, t.sop) for t in tasks]
        worst = max(range(len(tasks)), key=lambda i: stats[i][1])
        report["against"][name] = {
            "reference_sops": len(sops),
            "max_sop_jaccard": round(max(s[0] for s in stats), 3),
            "max_sentence_ratio": round(max(s[1] for s in stats), 3),
            "tasks_with_sentence_ratio_ge_0.75": sum(s[1] >= 0.75 for s in stats),
            "max_shared_8grams": max(s[2] for s in stats),
            "worst_sentence_task": tasks[worst].id,
        }
    print(json.dumps(report, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
