"""Held-out v2 report: every condition with a 95% Wilson interval, plus the one pre-registered comparison.

Usage: uv run python -m eval.final_v2_report label=path[#repaired] ... --primary LABEL_A LABEL_B --out file.json
A path ending in "#repaired" reads the repaired field of a repair-*.jsonl file; "#plain" reads its plain field.
Other files are baseline/constrained rows. Metric: safe_and_correct. The primary test is an exact McNemar.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.compare import mcnemar_exact, wilson


def load(spec: str) -> dict[str, tuple[bool, bool]]:
    """Return {task id: (safe_and_correct, is_trap)}."""
    path, _, field = spec.partition("#")
    out = {}
    for r in map(json.loads, Path(path).open(encoding="utf-8")):
        ok = r[field]["safe_and_correct"] if field else r["safe_and_correct"]
        out[r["id"]] = (bool(ok), r["trap"] != "none")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("conds", nargs="+")
    ap.add_argument("--primary", nargs=2, required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    runs = {c.split("=", 1)[0]: load(c.split("=", 1)[1]) for c in args.conds}
    ids = sorted(set.intersection(*(set(r) for r in runs.values())))
    table = {}
    for label, r in runs.items():
        k = sum(r[i][0] for i in ids)
        traps = [i for i in ids if r[i][1]]
        kt = sum(r[i][0] for i in traps)
        table[label] = {"correct": k, "n": len(ids), "rate": round(k / len(ids), 4), "ci95": wilson(k, len(ids)),
                        "traps_correct": kt, "traps_n": len(traps), "traps_ci95": wilson(kt, len(traps))}
    a, b = args.primary
    a_only = sum(1 for i in ids if runs[a][i][0] and not runs[b][i][0])
    b_only = sum(1 for i in ids if runs[b][i][0] and not runs[a][i][0])
    res = {"metric": "safe_and_correct", "n": len(ids), "conditions": table,
           "primary": {"a": a, "b": b, "a_only": a_only, "b_only": b_only,
                       "mcnemar_exact_p": mcnemar_exact(a_only, b_only)},
           "note": "Only the primary comparison is pre-registered; all other contrasts are exploratory."}
    print(json.dumps(res, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
