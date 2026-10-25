"""Paired comparison of two scored runs on the benchmark (safe_and_correct).

Usage: uv run python -m eval.compare <run_a.jsonl> <run_b.jsonl> [--out file.json]
Reports each run's count with a 95% Wilson interval and an exact two-sided McNemar test
on the tasks where exactly one run is correct.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _load(path: str) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, Path(path).open(encoding="utf-8")) if r["set"] == "benchmark"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, round(c - h, 3)), min(1.0, round(c + h, 3))


def mcnemar_exact(a_only: int, b_only: int) -> float:
    n = a_only + b_only
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(a_only, b_only) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare(a: str, b: str, key: str = "safe_and_correct") -> dict:
    ra, rb = _load(a), _load(b)
    ids = sorted(set(ra) & set(rb))
    ka, kb = sum(ra[i][key] for i in ids), sum(rb[i][key] for i in ids)
    a_only = sum(1 for i in ids if ra[i][key] and not rb[i][key])
    b_only = sum(1 for i in ids if rb[i][key] and not ra[i][key])
    traps = [i for i in ids if ra[i]["trap"] != "none"]
    return {"metric": key, "n": len(ids), "a": Path(a).name, "b": Path(b).name,
            "a_correct": ka, "a_ci95": wilson(ka, len(ids)), "b_correct": kb, "b_ci95": wilson(kb, len(ids)),
            "a_only": a_only, "b_only": b_only, "mcnemar_exact_p": mcnemar_exact(a_only, b_only),
            "traps_n": len(traps), "a_traps_correct": sum(ra[i][key] for i in traps),
            "b_traps_correct": sum(rb[i][key] for i in traps)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--out")
    args = ap.parse_args()
    res = compare(args.a, args.b)
    print(json.dumps(res, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2), encoding="utf-8")
