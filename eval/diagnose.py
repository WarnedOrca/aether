"""Stage 1 diagnosis: error taxonomy for one scored run on the development benchmark (non-trap tasks only).

Usage: uv run python -m eval.diagnose <run.jsonl> [--out file.json]
Each failing task gets exactly one class, from the first failing stage:
parse -> type/name -> disallowed column -> other checker rule -> wrong effect.
"Unfamiliar business" is a cross-cut: the task's business type is not one of the generator's training domains.
Dev split only; never run this on a held-out set.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

from data.gen.domains import DOMAINS
from eval.bench import load_tasks

CLASSES = {
    "parse": "does not parse",
    "type": "type or name error (E5xx, E601)",
    "column": "reads a sheet or column the policy does not allow (E401)",
    "rule": "other checker rule (approval, caps, batch mode, policy form)",
    "effect": "passes the checker but has different effects from the reference",
}


def classify(r: dict) -> str:
    d = r.get("detail") or ""
    if not r["parse"]:
        return "parse"
    if not r["check"]:
        code = re.search(r"\bE(\d{3})\b", d)
        c = code.group(1) if code else ""
        if c == "401":
            return "column"
        if c.startswith("5") or c == "601":
            return "type"
        return "rule"
    return "effect"


def parse_token(detail: str) -> str:
    m = re.search(r"Token\('(\w+)'", detail)
    return m.group(1) if m else "other"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--out")
    args = ap.parse_args()
    tasks = {t.id: t for t in load_tasks()}
    trained = {d.business.lower() for d in DOMAINS}
    rows = [json.loads(line) for line in Path(args.run).open(encoding="utf-8")]
    rows = [r for r in rows if r["set"] == "benchmark" and r["trap"] == "none"]
    fails = [r for r in rows if not r["safe_and_correct"]]
    by = collections.defaultdict(list)
    for r in fails:
        by[classify(r)].append(r)

    def familiar(r: dict) -> bool:
        return tasks[r["id"]].business.lower() in trained

    out = {"run": Path(args.run).name, "non_trap_tasks": len(rows), "solved": len(rows) - len(fails),
           "failed": len(fails), "classes": {}}
    for k, desc in CLASSES.items():
        rs = by.get(k, [])
        entry = {"description": desc, "count": len(rs), "unfamiliar_business": sum(not familiar(r) for r in rs),
                 "examples": [{"id": r["id"], "detail": (r.get("detail") or "")[:240]} for r in rs[:3]]}
        if k == "parse":
            entry["unexpected_tokens"] = collections.Counter(parse_token(r.get("detail") or "") for r in rs).most_common()
        if k == "effect":
            parts = [re.findall(r"scenario \d+/\w+( \(blank cells\))?: differs in \[([^\]]*)\]", r.get("detail") or "")
                     for r in rs]
            entry["blank_cells_only"] = sum(bool(p) and all(b for b, _ in p) for p in parts)
            entry["differs_in"] = collections.Counter(
                w.strip(" '") for p in parts for w in {x for _, s in p for x in s.split(",")}).most_common()
        if k in ("type", "rule"):
            entry["codes"] = collections.Counter(
                (re.search(r"\bE\d{3}\b", r.get("detail") or "") or [None])[0] for r in rs).most_common()
        out["classes"][k] = entry
    fam = [r for r in rows if familiar(r)]
    out["by_business"] = {"familiar_n": len(fam), "familiar_solved": sum(r["safe_and_correct"] for r in fam),
                          "unfamiliar_n": len(rows) - len(fam),
                          "unfamiliar_solved": sum(r["safe_and_correct"] for r in rows if not familiar(r))}
    print(json.dumps(out, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
