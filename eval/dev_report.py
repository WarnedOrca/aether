"""Dev-split report: several scored runs against one reference run (v0.2 rescored), all on eval/benchmark only.

For each run: correct (safe_and_correct) out of 110, non-trap (80), trap (30), parse rate, checker-pass rate, monitor problems,
paired exact McNemar p against the reference, memorisation count (outputs whose `about "..."` line is word-for-word an
`about` line of a training program) and forbidden-column count (checker code E401, i.e. a sheet/column the policy does not
allow). Never run this on a held-out set.

Usage: python -m eval.dev_report --reference <v0.2 rescored .jsonl> --train data/synthetic_v4 \
          --run label=<run .jsonl> [--run label=<run .jsonl> ...] --out eval/results/dev-report-<name>.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from eval.compare import compare, mcnemar_exact  # noqa: F401  (compare() is the paired test used everywhere else)

OLD_TRAIN_DIRS = ("data/synthetic", "data/synthetic_traps", "data/synthetic_v3")


def load(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def about_line(program: str) -> str | None:
    m = re.search(r'about "([^"]*)"', program or "")
    return m.group(1) if m else None


def forbidden_column(row: dict) -> bool:
    """The checker rejected the program for reading a sheet/column the policy does not allow (E401)."""
    return bool(row.get("parse")) and not row.get("check") and "E401" in (row.get("detail") or "")


def summarise(rows: list[dict], about_sets: dict[str, set[str]]) -> dict:
    rows = [r for r in rows if r["set"] == "benchmark"]
    non_trap, trap = [r for r in rows if r["trap"] == "none"], [r for r in rows if r["trap"] != "none"]
    out = {"n": len(rows),
           "correct": sum(r["safe_and_correct"] for r in rows),
           "non_trap_correct": sum(r["safe_and_correct"] for r in non_trap), "non_trap_n": len(non_trap),
           "trap_correct": sum(r["safe_and_correct"] for r in trap), "trap_n": len(trap),
           "parse_rate": round(sum(bool(r["parse"]) for r in rows) / len(rows), 4),
           "checker_pass_rate": round(sum(bool(r["check"]) for r in rows) / len(rows), 4),
           "forbidden_column_all": sum(forbidden_column(r) for r in rows),
           "forbidden_column_non_trap_failures": sum(forbidden_column(r) for r in non_trap if not r["safe_and_correct"])}
    for name, s in about_sets.items():
        out[f"about_reused_{name}"] = sum(about_line(r.get("program")) in s for r in rows if r.get("program"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True)
    ap.add_argument("--train", required=True, help="training data folder whose about lines count as memorised")
    ap.add_argument("--run", action="append", required=True, help="label=path.jsonl")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    new_train = {about_line(r["program"]) for s in ("train", "valid") for r in load(f"{args.train}/{s}.jsonl")}
    old_train = {about_line(r["program"]) for d in OLD_TRAIN_DIRS for r in load(f"{d}/train.jsonl")}
    sets = {"in_this_training_set": new_train, "in_older_template_sets": old_train}
    result = {"reference": args.reference, "training_data": args.train, "split": "eval/benchmark (dev) only", "runs": {}}
    ref_summary = summarise(load(args.reference), sets)
    result["reference_summary"] = ref_summary
    for item in args.run:
        label, path = item.split("=", 1)
        cmp = compare(args.reference, path)
        result["runs"][label] = {"file": path, **summarise(load(path), sets),
                                 "vs_reference": {"reference_only_correct": cmp["a_only"], "run_only_correct": cmp["b_only"],
                                                  "mcnemar_exact_p": round(cmp["mcnemar_exact_p"], 4)}}
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    cols = ("correct", "non_trap_correct", "trap_correct", "parse_rate", "about_reused_in_this_training_set", "forbidden_column_all")
    print("label".ljust(28), *[c[:18].ljust(19) for c in cols], "McNemar p")
    print("v0.2 (reference)".ljust(28), *[str(ref_summary[c]).ljust(19) for c in cols], "-")
    for label, r in result["runs"].items():
        print(label.ljust(28), *[str(r[c]).ljust(19) for c in cols], r["vs_reference"]["mcnemar_exact_p"])


if __name__ == "__main__":
    main()
