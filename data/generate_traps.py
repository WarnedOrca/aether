"""Generate trap-style training samples and drop any that overlap the benchmark or the held-out set.

Usage:  uv run python -m data.generate_traps [--n 450] [--seed 1]
Writes: data/synthetic_traps/{train,valid}.jsonl, overlap_report.json

Overlap check (against all 110 benchmark SOPs and all 30 held-out SOPs):
  - whole-SOP similarity: character 5-gram Jaccard; drop if >= 0.35
  - trap-sentence similarity: difflib ratio of each new trap sentence vs every reference sentence; drop if >= 0.75
    (the rest of each SOP comes from the same generator already used for v0.1)
  - shared word 8-grams anywhere in the SOP: drop if any
"""

from __future__ import annotations

import argparse
import difflib
import json
import random
import re
from collections import Counter
from pathlib import Path

from eval.bench import load_tasks

from .gen import patterns as P
from .gen import patterns2 as P2
from .gen import traps as T
from .gen.domains import DOMAINS, TEST_DOMAINS
from .generate import schema_block, verify

OUT = Path(__file__).resolve().parent / "synthetic_traps"
MESSAGING = {"reminder": P.reminder, "followup": P.followup, "lapsed": P.lapsed, "wait_followup": P2.wait_followup,
             "escalation": P2.escalation, "outreach": P2.outreach}
KINDS = ["skip-approval", "send-on-timeout", "unbounded", "reveal-private", "unlisted-recipient",
         "order-skip-approval", "over-limit", "unsupported-charge", "unsupported-payment",
         "unsupported-channel", "unsupported-post"]
SOP_JACCARD_MAX, SENT_RATIO_MAX = 0.35, 0.75


def _grams(text: str, n: int = 5) -> set[str]:
    t = re.sub(r"\s+", " ", text.lower())
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def _sentences(text: str) -> list[str]:
    return [s.strip().lower() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 15]


def _word_ngrams(text: str, n: int = 8) -> set[tuple]:
    w = re.findall(r"[a-z0-9$']+", text.lower())
    return {tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


class OverlapChecker:
    def __init__(self, references: list[str]):
        self.refs = [(_grams(r), _sentences(r), _word_ngrams(r)) for r in references]

    def check(self, sop: str, trap_text: str) -> tuple[float, float, int]:
        g, sents, ngr = _grams(sop), _sentences(trap_text), _word_ngrams(sop)
        best_j = max(len(g & rg) / len(g | rg) for rg, _, _ in self.refs)
        best_s = 0.0
        for _, rs, _ in self.refs:
            for a in sents:
                for b in rs:
                    sm = difflib.SequenceMatcher(None, a, b)
                    if sm.real_quick_ratio() > best_s and sm.quick_ratio() > best_s:
                        best_s = max(best_s, sm.ratio())
        shared = max(len(ngr & rn) for _, _, rn in self.refs)
        return best_j, best_s, shared


def make(kind: str, d, rng: random.Random) -> P.Sample | None:
    if kind.startswith("unsupported"):
        return T.unsupported(d, rng, kind)
    if kind == "order-skip-approval":
        base = P.reorder(d, rng, False)
    elif kind == "over-limit":
        base = P.refund(d, rng, False)
    else:
        fn = MESSAGING[rng.choice(sorted(MESSAGING))]
        base = fn(d, rng, rng.random() < 0.3 and fn in (P.reminder, P.followup, P.lapsed, P2.outreach))
    return T.apply_trap(kind, base, d, rng) if base else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=450)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    refs = [t.sop for t in load_tasks()] + [t.sop for t in load_tasks(Path("eval/heldout"))]
    checker = OverlapChecker(refs)
    domains = [d for d in DOMAINS if d.name not in TEST_DOMAINS]
    kept, dropped, seen, sims = [], Counter(), set(), []
    attempts = 0
    while len(kept) < args.n and attempts < args.n * 20:
        attempts += 1
        kind = KINDS[attempts % len(KINDS)]
        s = make(kind, rng.choice(domains), rng)
        if s is None:
            dropped["not applicable"] += 1
            continue
        if s.sop in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(s.sop)
        why = verify(s)
        if why:
            dropped[f"verify: {why.split(':')[0]}"] += 1
            continue
        j, r, shared = checker.check(s.sop, s.meta["trap_text"])
        sims.append((j, r))
        if j >= SOP_JACCARD_MAX or r >= SENT_RATIO_MAX or shared:
            dropped["overlap"] += 1
            continue
        kept.append(s)
    OUT.mkdir(parents=True, exist_ok=True)
    rng.shuffle(kept)
    n_valid = max(20, len(kept) // 12)
    for split, rows in (("valid", kept[:n_valid]), ("train", kept[n_valid:])):
        with open(OUT / f"{split}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for i, s in enumerate(rows):
                f.write(json.dumps({"id": f"trap-{split}-{i:05d}", "domain": s.domain, "pattern": s.pattern,
                                    "trap": s.meta["trap"], "batch": s.meta.get("batch", False), "sop": s.sop,
                                    "policy": s.policy, "sheets": schema_block(s.program),
                                    "program": s.program}) + "\n")
    js, rs = sorted(j for j, _ in sims), sorted(r for _, r in sims)
    report = {"seed": args.seed, "kept": len(kept), "train": len(kept) - n_valid, "valid": n_valid,
              "dropped": dict(dropped), "by_kind": dict(Counter(s.meta["trap"] for s in kept)),
              "references": {"benchmark_sops": 110, "heldout_sops": 30},
              "thresholds": {"sop_char5_jaccard_max": SOP_JACCARD_MAX, "trap_sentence_ratio_max": SENT_RATIO_MAX,
                             "shared_word_8grams": 0},
              "checked_samples": len(sims),
              "sop_jaccard": {"median": js[len(js) // 2], "p99": js[int(len(js) * 0.99)], "max": js[-1]},
              "trap_sentence_ratio": {"median": rs[len(rs) // 2], "p99": rs[int(len(rs) * 0.99)], "max": rs[-1]}}
    (OUT / "overlap_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
