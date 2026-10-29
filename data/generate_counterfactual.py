"""Counterfactual seed programs: the column a program would naturally filter on is NOT allowed by the policy.

Made by script from the existing seed programs (data/synthetic, data/synthetic_traps, data/synthetic_v3), with no new
English text: for a program whose filter reads column C in exactly one condition (and nowhere else),
  - drop that condition from the filter (at least one other condition must remain),
  - remove C from the policy's `allow read` list for that sheet (write permission, if any, is kept),
  - keep C in the sheet declaration, so the model sees the tempting column but must not use it.
Every result must parse, pass the checker and run clean under the monitor (data.generate.verify, 3 seeds).
Programs are picked round-robin over columns (not mostly `status`) with a fixed seed, one per seed program.
Rejected if the program, its sheet declaration or its `about` line equals one from a dev or held-out task.

Output: <out>/train.jsonl (stage 3 seed format, sop left empty) and <out>/summary.json, with provenance per row.
Usage: python -m data.generate_counterfactual --n 534 --max-per-column 300 --out data/synthetic_cf
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ("data/synthetic", "data/synthetic_traps", "data/synthetic_v3")
EVAL_DIRS = ("eval/benchmark", "eval/heldout", "eval/heldout2", "eval/heldout3")
FILTER = re.compile(r"^(\s*let \w+ = filter (\w+) where )(.+)$")


def sheet_line(program: str) -> str:
    return "\n".join(l.strip() for l in program.splitlines() if l.strip().startswith("sheet "))


def about(program: str) -> str | None:
    m = re.search(r'about "([^"]*)"', program)
    return m.group(1) if m else None


def fetched_sheet(program: str, var: str) -> str | None:
    """The sheet behind `let <var> = fetch <Sheet>` (or a filter of such a variable)."""
    m = re.search(rf"let {var} = fetch (\w+)", program)
    if m:
        return m.group(1)
    m = re.search(rf"let {var} = filter (\w+) where", program)
    return fetched_sheet(program, m.group(1)) if m else None


def variants(seed: dict) -> list[dict]:
    """All single-column counterfactuals of one seed program (before verification)."""
    program, policy = seed["program"], seed["policy"]
    lines = program.splitlines()
    out = []
    for i, line in enumerate(lines):
        m = FILTER.match(line)
        if not m or " or " in m.group(3) or "(" in m.group(3).replace("date_of(", "").replace("today()", "").replace("time_of(", ""):
            continue
        sheet = fetched_sheet(program, m.group(2))
        if not sheet:
            continue
        allow = re.search(rf"allow read {sheet}\(([^)]*)\)", policy)
        if not allow:
            continue
        allowed = [c.strip() for c in allow.group(1).split(",")]
        conjuncts = m.group(3).split(" and ")
        if len(conjuncts) < 2:
            continue
        for k, conj in enumerate(conjuncts):
            for col in allowed:
                if not re.search(rf"\b{col}\b", conj) or sum(bool(re.search(rf"\b{col}\b", c)) for c in conjuncts) != 1:
                    continue
                rest = conjuncts[:k] + conjuncts[k + 1:]
                new_lines = lines[:i] + [m.group(1) + " and ".join(rest)] + lines[i + 1:]
                body = [l for j, l in enumerate(new_lines) if not l.strip().startswith("sheet ")]
                if any(re.search(rf"\b{col}\b", re.sub(rf"set {col} =", "", l)) for l in body):
                    continue  # the column is still read somewhere else (message, another filter, a summary ...)
                if len(allowed) < 2:
                    continue
                new_allow = f"allow read {sheet}(" + ", ".join(c for c in allowed if c != col) + ")"
                out.append({"program": "\n".join(new_lines), "policy": policy.replace(allow.group(0), new_allow),
                            "column": col, "sheet": sheet, "dropped_condition": conj.strip()})
    return out


def load_seeds() -> list[dict]:
    seeds = []
    for src in SOURCES:
        for line in (ROOT / src / "train.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            seeds.append({**r, "source": f"{src}/train.jsonl", "trap": r.get("trap", "none")})
    return seeds


def eval_index() -> dict[str, set]:
    from eval.bench import load_tasks
    idx = {"program": set(), "sheet": set(), "about": set()}
    for d in EVAL_DIRS:  # read only, to make sure nothing overlaps an evaluation task
        for t in load_tasks(ROOT / d):
            idx["program"].add(re.sub(r"\s+", " ", t.program).strip())
            idx["sheet"].add(sheet_line(t.program))
            idx["about"].add(about(t.program))
    return idx


def overlaps(program: str, idx: dict[str, set]) -> str:
    if re.sub(r"\s+", " ", program).strip() in idx["program"]:
        return "program"
    if sheet_line(program) in idx["sheet"]:
        return "sheet declaration"
    if about(program) in idx["about"]:
        return "about line"
    return ""


def select(cands: list[dict], n: int, seed: int, max_per_column: int = 0) -> list[dict]:
    """Round-robin over columns (shuffled within each column), at most one counterfactual per seed program, and at most
    `max_per_column` per column (0 = no cap), so one common column (status) does not dominate."""
    rng = random.Random(seed)
    by_col: dict[str, list[dict]] = collections.defaultdict(list)
    for c in cands:
        by_col[c["column"]].append(c)
    for v in by_col.values():
        rng.shuffle(v)
    cols = sorted(by_col)
    rng.shuffle(cols)
    picked, used = [], set()
    while len(picked) < n and any(by_col.values()):
        for col in cols:
            while by_col[col] and by_col[col][0]["seed_id"] in used:
                by_col[col].pop(0)
            if max_per_column and sum(p["column"] == col for p in picked) >= max_per_column:
                by_col[col].clear()
            if by_col[col] and len(picked) < n:
                c = by_col[col].pop(0)
                used.add(c["seed_id"])
                picked.append(c)
    return picked


def main() -> None:
    from data.gen.patterns import Sample
    from data.generate import verify

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=620)
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--max-per-column", type=int, default=300)
    ap.add_argument("--out", default="data/synthetic_cf")
    args = ap.parse_args()
    idx = eval_index()
    reasons = collections.Counter()
    cands = []
    for s in load_seeds():
        for v in variants(s):
            ov = overlaps(v["program"], idx)
            bad = "overlap: " + ov if ov else verify(Sample("cf", s.get("domain", ""), "", v["policy"], v["program"]))
            if bad:
                reasons[bad.split(":")[0] + (":" + bad.split(":")[1][:20] if bad.startswith("overlap") else "")] += 1
                continue
            cands.append({**v, "seed_id": s["id"], "seed": s})
    picked = select(cands, args.n, args.seed, args.max_per_column)
    v4 = ROOT / "data/synthetic_v4/train.jsonl"
    v4_text = v4.read_text(encoding="utf-8") if v4.exists() else ""
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for c in picked:
        s = c["seed"]
        rows.append({"id": f"cf-{s['id']}-{c['column']}", "domain": s.get("domain", ""), "trap": s["trap"],
                     "sop": "", "policy": c["policy"], "sheets": s["sheets"], "program": c["program"],
                     "provenance": {"generator": "data/generate_counterfactual.py", "transform": "drop-filter-column",
                                    "seed_program": s["id"], "seed_source": s["source"], "column_not_allowed": c["column"],
                                    "sheet": c["sheet"], "dropped_condition": c["dropped_condition"], "selection_seed": args.seed,
                                    "verified": "parse + checker + monitored run (3 seeds)", "hosted_ai_text": False}})
    with (out / "train.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    cols = collections.Counter(r["provenance"]["column_not_allowed"] for r in rows)
    summary = {"rows": len(rows), "candidates_verified": len(cands), "rejected": dict(reasons),
               "distinct_columns": len(cols), "columns": dict(cols.most_common()),
               "columns_never_in_v4_train_text": sorted(c for c in cols if not re.search(rf"\b{c}\b", v4_text)),
               "traps": sum(r["trap"] != "none" for r in rows), "seed_programs_already_in_v4_train":
                   sum(f'"{r["provenance"]["seed_program"]}#' in v4_text for r in rows),
               "selection_seed": args.seed, "max_per_column": args.max_per_column, "hosted_ai_text_used": False}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "columns"}, indent=2))
    print("top columns:", cols.most_common(12))


if __name__ == "__main__":
    main()
