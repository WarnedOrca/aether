"""Merge the counterfactual wordings (data/synthetic_v4_cf) into data/synthetic_v4 (the only folder stage 4 trains on).

train.jsonl / valid.jsonl in data/synthetic_v4 are rebuilt from BOTH record files with the same split rule as stage 3:
the old accepted rows are unchanged, the new accepted rows are added, and each new row gets the counterfactual
provenance (seed program, forbidden column, dropped condition) from data/synthetic_cf. Rerunning gives the same files.
Note: rerunning stage 3 on data/synthetic_v4 alone rewrites train/valid WITHOUT the new rows; run this merge again then.

Usage: python -m stages.merge_cf [--v4 data/synthetic_v4] [--cf data/synthetic_v4_cf] [--cf-seeds data/synthetic_cf]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stages.common import ROOT, write_json
from stages.stage3_paraphrase import build_splits, write_splits


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix() if path.resolve().is_relative_to(ROOT) else path.as_posix()


def read_records(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def merge(v4: Path, cf: Path, cf_seeds: Path) -> dict:
    old = build_splits(read_records(v4 / "records.jsonl"))
    new = build_splits(read_records(cf / "records.jsonl"))
    seeds = {json.loads(l)["id"]: json.loads(l)["provenance"] for l in (cf_seeds / "train.jsonl").read_text(encoding="utf-8").splitlines()}
    for split in new.values():
        for r in split:
            r["provenance"] = {**r["provenance"], "counterfactual": seeds[r["id"].split("#")[0]]}
    ids_old = {r["id"] for s in old.values() for r in s}
    clash = ids_old & {r["id"] for s in new.values() for r in s}
    if clash:
        raise ValueError(f"ids in both sets: {sorted(clash)[:5]}")
    rows = {k: old[k] + new[k] for k in old}
    write_splits(v4, rows)
    n_old, n_new = sum(map(len, old.values())), sum(map(len, new.values()))
    info = {"old_rows": {k: len(v) for k, v in old.items()}, "new_rows": {k: len(v) for k, v in new.items()},
            "new_share": round(n_new / (n_old + n_new), 4),
            "new_trap_rows": sum(r["trap"] != "none" for s in new.values() for r in s),
            "merged_from": [rel(cf), rel(cf_seeds)]}
    summary_path = v4 / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["counterfactual_merge"] = info
    summary["train"], summary["valid"] = len(rows["train"]), len(rows["valid"])
    write_json(summary_path, summary)
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v4", default="data/synthetic_v4")
    ap.add_argument("--cf", default="data/synthetic_v4_cf")
    ap.add_argument("--cf-seeds", default="data/synthetic_cf")
    args = ap.parse_args()
    print(json.dumps(merge(ROOT / args.v4, ROOT / args.cf, ROOT / args.cf_seeds), indent=2))


if __name__ == "__main__":
    main()
