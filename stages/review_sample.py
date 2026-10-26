"""Draw a fixed-seed random sample of accepted wordings for the owner to read (nobody hand-picks them).

Usage: python -m stages.review_sample data/synthetic_v4 --n 30 --seed 20261027 --out docs/review/wordings-sample-2026-10-27.md
Reads train.jsonl and valid.jsonl (accepted wordings only), draws N without replacement with random.Random(seed),
and writes the field `sop` next to the program id (the wording's key, e.g. <seed program>#<k>) and its trap kind.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from stages.common import ROOT


def pick_sample(rows: list[dict], n: int, seed: int) -> list[dict]:
    """N rows drawn without replacement from rows sorted by id (so the draw does not depend on file order), listed in id order."""
    pool = sorted(rows, key=lambda r: r["id"])
    return sorted(random.Random(seed).sample(pool, min(n, len(pool))), key=lambda r: r["id"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20261027)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rows = []
    for split in ("train", "valid"):
        rows += [json.loads(l) for l in (ROOT / args.data_dir / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    sample = pick_sample(rows, args.n, args.seed)
    lines = [f"# Random sample of {len(sample)} accepted wordings ({args.data_dir})", "",
             f"Drawn by `python -m stages.review_sample {args.data_dir} --n {args.n} --seed {args.seed}` from {len(rows)} accepted "
             "wordings (train + valid) with Python's `random.Random(seed).sample`; nobody picked them by hand. "
             "Each entry shows the wording (`sop` field), its id (seed program + wording number) and its trap kind. "
             "These wordings were written by a local open-weight model (Qwen2.5-7B-Instruct) from the program only; the automatic "
             "filters are structural, so please judge whether each wording really asks for what the program does "
             "(and, for trap kinds, really asks for the unsafe thing).", ""]
    for i, r in enumerate(sample, 1):
        lines += [f"## {i}. `{r['id']}` (trap kind: {r['trap']})", "", r["sop"].strip(), ""]
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {len(sample)} wordings to {args.out}")


if __name__ == "__main__":
    main()
