"""v0.3 training data: the same verified generators applied to 30 new business types.

Usage: uv run python -m data.generate_v3 [--per-combo 3] [--traps 250]
Writes data/synthetic_v3/{train,valid}.jsonl and report.json.

Every sample must pass the generator's verify() (parse, checker, clean runs). Samples
are dropped if they are too close to any evaluation SOP (benchmark, held-out v1,
held-out v2): whole-SOP char-5-gram Jaccard >= 0.35 or any shared word 8-gram.
Trap samples also need their trap sentence below a difflib ratio of 0.75.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from eval.bench import load_tasks

from .gen import traps as T
from .gen.domains2 import NEW_DOMAINS
from .generate import BATCHABLE, PATTERNS, schema_block, verify
from .generate_traps import KINDS, OverlapChecker, make

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "synthetic_v3"


def eval_businesses() -> set[str]:
    names = set()
    for d in ("eval/benchmark", "eval/heldout", "eval/heldout2"):
        names |= {t.business.lower() for t in load_tasks(ROOT / d)}
    return names


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-combo", type=int, default=3)
    ap.add_argument("--traps", type=int, default=250)
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    clash = {d.business for d in NEW_DOMAINS} & eval_businesses()
    assert not clash, f"business types also used in evaluation sets: {clash}"
    refs = [t.sop for d in ("eval/benchmark", "eval/heldout", "eval/heldout2") for t in load_tasks(ROOT / d)]
    checker = OverlapChecker(refs)
    kept, dropped = [], Counter()

    def consider(s, trap_text: str | None):
        if s is None:
            dropped["not applicable"] += 1
            return
        why = verify(s)
        if why:
            dropped["verify: " + why.split(":")[0]] += 1
            return
        j, r, shared = checker.check(s.sop, trap_text or "")
        if j >= 0.35 or shared or (trap_text and r >= 0.75):
            dropped["overlap with evaluation sets"] += 1
            return
        kept.append(s)

    for d in NEW_DOMAINS:
        for fn_name, fn in PATTERNS.items():
            for batch in ([False, True] if fn_name in BATCHABLE else [False]):
                for _ in range(args.per_combo):
                    consider(fn(d, rng, batch), None)
    n_before = len(kept)
    attempts = 0
    while len(kept) - n_before < args.traps and attempts < args.traps * 10:
        attempts += 1
        s = make(KINDS[attempts % len(KINDS)], rng.choice(NEW_DOMAINS), rng)
        consider(s, s.meta.get("trap_text") if s else None)
    seen, unique = set(), []
    for s in kept:
        if s.sop not in seen:
            seen.add(s.sop)
            unique.append(s)
    rng.shuffle(unique)
    n_valid = max(30, len(unique) // 15)
    OUT.mkdir(parents=True, exist_ok=True)
    for split, rows in (("valid", unique[:n_valid]), ("train", unique[n_valid:])):
        with open(OUT / f"{split}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for i, s in enumerate(rows):
                f.write(json.dumps({"id": f"v3-{split}-{i:05d}", "domain": s.domain, "pattern": s.pattern,
                                    "trap": s.meta.get("trap", "none"), "batch": s.meta.get("batch", False),
                                    "sop": s.sop, "policy": s.policy, "sheets": schema_block(s.program),
                                    "program": s.program}) + "\n")
    report = {"seed": args.seed, "new_business_types": len(NEW_DOMAINS), "kept": len(unique),
              "train": len(unique) - n_valid, "valid": n_valid, "dropped": dict(dropped),
              "traps": sum(1 for s in unique if s.meta.get("trap")),
              "by_pattern": dict(Counter(s.pattern for s in unique))}
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
