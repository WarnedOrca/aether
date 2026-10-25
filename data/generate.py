"""Generate the synthetic SOP -> Aether dataset and keep only verified samples.

Usage:  uv run python -m data.generate [--per-combo 6] [--seed 0]
Writes: data/synthetic/{train,valid,test}.jsonl and data/synthetic/stats.json

A sample is kept only if its program parses, passes the checker with zero
errors, and runs on 3 random workspaces with no run error, no refusal, and no
monitor violation. Test samples come only from held-out business domains.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from checker.check import check
from checker.diagnostics import errors
from checker.parser import parse_source
from interpreter.sandbox import run_monitored, workspace_for

from .gen import patterns as P
from .gen import patterns2 as P2
from .gen.domains import DOMAINS, TEST_DOMAINS

PATTERNS = {
    "reminder": P.reminder, "followup": P.followup, "lapsed": P.lapsed, "summary": P.summary,
    "reorder": P.reorder, "refund": P.refund, "confirm_new": P2.confirm_new,
    "wait_followup": P2.wait_followup, "escalation": P2.escalation, "outreach": P2.outreach,
}
BATCHABLE = {"reminder", "followup", "lapsed", "outreach"}
OUT = Path(__file__).resolve().parent / "synthetic"


def verify(sample: P.Sample) -> str:
    """Empty string if the sample is good, else the reason it was dropped."""
    try:
        src = parse_source(sample.policy + "\n" + sample.program)
    except Exception as exc:  # noqa: BLE001 - any parse failure drops the sample
        return f"parse: {exc}"
    (proc,) = src.procedures.values()
    pol = src.policies[proc.policy]
    errs = errors(check(proc, pol))
    if errs:
        return f"check: {errs[0]}"
    for seed in range(3):
        ws = workspace_for(proc, rng=random.Random(seed), rows=6)
        out = run_monitored(proc, pol, ws, params={"days": 60})
        if out.result.status in ("error", "refused"):
            return f"run: {out.result.status} {out.result.reason[:80]}"
        if out.problems:
            return f"monitor: {out.problems[0]}"
    return ""


def schema_block(program: str) -> str:
    """The sheet/calendar declarations: the model gets these as input (the owner's workspace)."""
    return "\n".join(line.strip() for line in program.splitlines()
                     if line.strip().startswith(("sheet ", "calendar ")))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-combo", type=int, default=6)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    kept, dropped, seen = [], Counter(), set()
    for d in DOMAINS:
        for pname, fn in PATTERNS.items():
            modes = [False, True] if pname in BATCHABLE else [False]
            for batch in modes:
                for _ in range(args.per_combo):
                    s = fn(d, rng, batch)
                    if s is None:
                        break
                    key = hashlib.sha256((s.sop + s.program).encode()).hexdigest()
                    if key in seen:
                        dropped["duplicate"] += 1
                        continue
                    seen.add(key)
                    why = verify(s)
                    if why:
                        dropped[why.split(":")[0]] += 1
                        if dropped[why.split(":")[0]] <= 3:
                            print("DROPPED", pname, d.name, why)
                        continue
                    kept.append(s)
    splits = {"train": [], "valid": [], "test": []}
    for s in kept:
        if s.domain in TEST_DOMAINS:
            split = "test"
        else:
            split = "valid" if rng.random() < 0.08 else "train"
        splits[split].append(s)
    OUT.mkdir(parents=True, exist_ok=True)
    for split, rows in splits.items():
        with open(OUT / f"{split}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for i, s in enumerate(rows):
                f.write(json.dumps({"id": f"{split}-{i:05d}", "domain": s.domain, "pattern": s.pattern,
                                    "batch": s.meta.get("batch", False), "sop": s.sop, "policy": s.policy,
                                    "sheets": schema_block(s.program), "program": s.program}) + "\n")
    stats = {"seed": args.seed, "per_combo": args.per_combo, "kept": len(kept), "dropped": dict(dropped),
             "splits": {k: len(v) for k, v in splits.items()},
             "patterns": dict(Counter(s.pattern for s in kept)), "test_domains": sorted(TEST_DOMAINS)}
    (OUT / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
