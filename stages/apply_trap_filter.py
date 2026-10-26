"""Apply the tightened trap-ask filter (stage 3 acceptance filter f2-tight-trap) to an existing stage 3 output folder.

data/synthetic_v4 was first built with an older, leakier filter. This script re-checks every accepted wording with the
current `trap_ask_missing`, marks the ones that fail as rejected ("trap ask missing") in records.jsonl, copies their full
original records (wording, program and provenance) to removed_rows.jsonl, and rebuilds train.jsonl / valid.jsonl and
summary.json from the remaining accepted records. Nothing is deleted: the untouched records.jsonl is kept as
records.before-trap-filter.jsonl the first time the script changes anything. Running it again changes nothing.

Usage: python -m stages.apply_trap_filter data/synthetic_v4 [--expect-keys-from eval/results/<gate>.json]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from stages.common import ROOT, write_json
from stages.stage3_paraphrase import FILTER_VERSION, build_splits, trap_ask_missing, write_splits

REASON = "trap ask missing"


def flagged(records: list[dict]) -> list[dict]:
    return [r for r in records if r["accepted"] and trap_ask_missing(r["trap"], r["sop"])]


def apply_filter(data_dir: Path, expect_keys: set[str] | None = None) -> dict:
    """Returns {"removed": [...keys], "train": n, "valid": n}. Raises if `expect_keys` differs from what the filter flags."""
    records = [json.loads(line) for line in (data_dir / "records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    bad = flagged(records)
    keys = {r["key"] for r in bad}
    if expect_keys is not None and keys != expect_keys:
        raise ValueError(f"filter flags {len(keys)} rows but the expected list has {len(expect_keys)}; "
                         f"only-filter {sorted(keys - expect_keys)[:5]}, only-list {sorted(expect_keys - keys)[:5]}")
    if bad:
        backup = data_dir / "records.before-trap-filter.jsonl"
        if not backup.exists():
            shutil.copyfile(data_dir / "records.jsonl", backup)
        with (data_dir / "removed_rows.jsonl").open("a", encoding="utf-8", newline="\n") as f:
            for r in bad:
                f.write(json.dumps({**r, "removed_by": "stages.apply_trap_filter", "removed_filter": FILTER_VERSION,
                                    "removed_reason": REASON}) + "\n")
        new_records = [{**r, "accepted": False, "reject_reason": REASON, "originally_accepted": True,
                        "rejected_by_filter": FILTER_VERSION} if r["key"] in keys else r for r in records]
        tmp = data_dir / "records.jsonl.tmp"
        tmp.write_text("".join(json.dumps(r) + "\n" for r in new_records), encoding="utf-8", newline="\n")
        os.replace(tmp, data_dir / "records.jsonl")
        records = new_records
    rows = build_splits(records)
    write_splits(data_dir, rows)
    summary_path = data_dir / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        reasons: dict[str, int] = {}
        for r in records:
            if not r["accepted"]:
                k = r["reject_reason"].split(" [")[0].split(":")[0]
                reasons[k] = reasons.get(k, 0) + 1
        summary.update(records=len(records), accepted=sum(r["accepted"] for r in records), train=len(rows["train"]),
                       valid=len(rows["valid"]), rejected_by_reason=reasons)
        removed_total = sum(1 for r in records if r.get("originally_accepted"))
        if removed_total:
            summary["removed_by_tightened_trap_filter"] = removed_total
        write_json(summary_path, summary)
    return {"removed": sorted(keys), "train": len(rows["train"]), "valid": len(rows["valid"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("--expect-keys-from", default="", help="quality-gate JSON whose trap_ask_present violations must equal the flagged keys")
    args = ap.parse_args()
    expect = None
    if args.expect_keys_from:
        gate = json.loads((ROOT / args.expect_keys_from).read_text(encoding="utf-8"))
        expect = set(gate["checks"]["trap_ask_present"]["violations"])
    result = apply_filter(ROOT / args.data_dir, expect)
    print(f"removed {len(result['removed'])} rows; train {result['train']}, valid {result['valid']}")


if __name__ == "__main__":
    main()
