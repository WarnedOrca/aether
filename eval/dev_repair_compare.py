"""EXPLORATORY dev-only comparison of two checker-feedback (repair) runs on the same tasks.

Reports, for each run, plain and repaired `safe_and_correct` counts (all / non-trap / trap) and monitor problems,
the exact McNemar test of repaired vs repaired, and of each run's repaired vs its own plain outputs.
Not confirmatory: nothing was declared in advance for this comparison, and it is on the dev split.

Usage: python -m eval.dev_repair_compare --a label=repair.jsonl --b label=repair.jsonl --out eval/results/<name>.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.compare import mcnemar_exact, wilson


def load(path: str) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines())}


def counts(rows: dict[str, dict], which: str) -> dict:
    ok = {i: bool(r[which]["safe_and_correct"]) for i, r in rows.items()}
    return {"all": sum(ok.values()), "non_trap": sum(v for i, v in ok.items() if rows[i]["trap"] == "none"),
            "trap": sum(v for i, v in ok.items() if rows[i]["trap"] != "none")}


def paired(a: dict[str, bool], b: dict[str, bool]) -> dict:
    a_only = sum(a[i] and not b[i] for i in a)
    b_only = sum(b[i] and not a[i] for i in a)
    return {"a_only": a_only, "b_only": b_only, "mcnemar_exact_p": round(mcnemar_exact(a_only, b_only), 4)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    (la, pa), (lb, pb) = args.a.split("=", 1), args.b.split("=", 1)
    ra, rb = load(pa), load(pb)
    if set(ra) != set(rb):
        raise ValueError("the two runs cover different tasks")
    n = len(ra)
    rep = lambda rows: {i: bool(r["repaired"]["safe_and_correct"]) for i, r in rows.items()}
    pla = lambda rows: {i: bool(r["plain"]["safe_and_correct"]) for i, r in rows.items()}
    out = {"status": "EXPLORATORY (dev split, not pre-registered; not confirmatory)", "n": n,
           "protocol": "eval.repair: parser + checker feedback only, up to 3 rounds, greedy", "files": {la: pa, lb: pb}, "runs": {}}
    for label, rows in ((la, ra), (lb, rb)):
        c = counts(rows, "repaired")
        out["runs"][label] = {"plain_correct": counts(rows, "plain"), "repaired_correct": c,
                              "repaired_ci95": wilson(c["all"], n),
                              "rounds_used": {k: sum(r["rounds_used"] == k for r in rows.values()) for k in range(4)},
                              "monitor_problems_total": sum(len(r["monitor_problems"]) for r in rows.values()),
                              "repaired_vs_own_plain": paired(rep(rows), pla(rows))}
    out["repaired_a_vs_repaired_b"] = {"a": la, "b": lb, **paired(rep(ra), rep(rb))}
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
