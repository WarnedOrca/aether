"""Quality gate for stage 3 wordings (replaces owner review of the smoke output).

Checks the first N records of <data dir>/records.jsonl against the gate declared in HANDOFF.md:
  1. acceptance rate >= 20%
  2. no accepted wording contains code
  3. every accepted wording states every cap/amount/time of its program, and invents no numbers
  4. accepted trap wordings contain the trap's ask
  5. at most 5% of accepted wordings are near-copies (5-character-gram Jaccard >= 0.6) of the generator's English
     for the same program (that English is only used here, to measure copying; it never reaches the model)
Usage: python -m stages.quality_gate data/synthetic_v4 --first 200 --out eval/results/stage3-quality-gate.json
Prints PASS/FAIL per check, exits 1 if any fails.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from stages.common import ROOT, write_json
from stages.stage3_paraphrase import CODE, grams, invented_numbers, missing_times, numbers_needed, trap_ask_missing

MIN_ACCEPT = 0.20
NEAR_COPY = 0.6
MAX_NEAR_COPY_SHARE = 0.05


def original_sops(sources: list[str]) -> dict[str, str]:
    out = {}
    for src in sources:
        for line in (ROOT / src / "train.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            out[r["id"]] = r["sop"]
    return out


def evaluate(records: list[dict], originals: dict[str, str]) -> dict:
    accepted = [r for r in records if r["accepted"]]
    code = [r["key"] for r in accepted if CODE.search(r["sop"])]
    incomplete, invented, trap_missing, copies = [], [], [], []
    sims = []
    for r in accepted:
        text = r["sop"]
        if [x for x in numbers_needed(r["program"]) if not re.search(rf"\b{x}\b", text)] or missing_times(r["program"], text):
            incomplete.append(r["key"])
        if invented_numbers(r["program"] + "\n" + r["policy"], text):
            invented.append(r["key"])
        if trap_ask_missing(r["trap"], text):
            trap_missing.append(r["key"])
        orig = originals.get(r["seed_id"])
        if orig:
            a, b = grams(text), grams(orig)
            sims.append(len(a & b) / max(len(a | b), 1))
            if sims[-1] >= NEAR_COPY:
                copies.append(r["key"])
    rate = len(accepted) / max(len(records), 1)
    checks = {
        "acceptance_rate": {"value": round(rate, 3), "pass": rate >= MIN_ACCEPT},
        "no_code": {"violations": code, "pass": not code},
        "states_every_amount_cap_time": {"violations": incomplete, "pass": not incomplete},
        "no_invented_numbers": {"violations": invented, "pass": not invented},
        "trap_ask_present": {"violations": trap_missing, "pass": not trap_missing},
        "not_near_copies": {"near_copies": copies, "max_similarity": round(max(sims, default=0), 3),
                            "mean_similarity": round(sum(sims) / max(len(sims), 1), 3),
                            "pass": len(copies) <= MAX_NEAR_COPY_SHARE * max(len(accepted), 1)},
    }
    by_reason: dict[str, int] = {}
    for r in records:
        if not r["accepted"]:
            k = r["reject_reason"].split(" [")[0].split(":")[0]
            by_reason[k] = by_reason.get(k, 0) + 1
    return {"attempts": len(records), "accepted": len(accepted), "rejected_by_reason": by_reason,
            "checks": checks, "passed": all(c["pass"] for c in checks.values())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("--first", type=int, default=0, help="only the first N attempts (0 = all)")
    ap.add_argument("--sources", nargs="+", default=["data/synthetic", "data/synthetic_traps", "data/synthetic_v3"])
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    records = [json.loads(line) for line in (ROOT / args.data_dir / "records.jsonl").open(encoding="utf-8") if line.strip()]
    if args.first:
        records = records[: args.first]
    result = evaluate(records, original_sops(args.sources))
    result["data_dir"], result["first"] = args.data_dir, args.first
    for name, c in result["checks"].items():
        print("PASS" if c["pass"] else "FAIL", name, {k: v for k, v in c.items() if k != "pass"})
    print(f"attempts={result['attempts']} accepted={result['accepted']} rejected_by_reason={result['rejected_by_reason']}")
    if args.out:
        write_json(ROOT / args.out, result)
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
