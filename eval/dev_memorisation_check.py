"""Dev-only memorisation check from SAVED outputs (CPU only, no model is run).

For each output whose `about "..."` line is word-for-word an `about` line of a training program:
  - skeleton similarity to the closest training program with that about line: both programs are reduced to their
    statement skeleton (keywords and operators; names, strings and numbers become placeholders) and compared with
    difflib's ratio (1.0 = identical structure);
  - the same similarity to the task's reference program, as a yardstick (a correct program should look like it);
  - whether the output is correct, compared with outputs that do not reuse an about line.
Never run this on a held-out set.

Usage: python -m eval.dev_memorisation_check --run label=path.jsonl [...] --out eval/results/dev-memorisation-<date>.json
"""

from __future__ import annotations

import argparse
import collections
import difflib
import json
import re
from pathlib import Path

from eval.bench import load_tasks
from eval.dev_report import about_line

KEYWORDS = {"procedure", "about", "policy", "sheet", "trigger", "every", "day", "at", "let", "fetch", "filter", "where",
            "for", "each", "in", "up", "to", "draft", "sms", "email", "request", "approval", "of", "from", "owner",
            "timeout", "else", "skip", "send", "update", "set", "append", "summarize", "if", "and", "or", "not",
            "default", "count", "sum", "today", "days", "hours", "batch", "notify"}
TOKEN = re.compile(r'"[^"]*"|\d+(?:\.\d+)?|\$[\d.]+|\w+|==|!=|<=|>=|[{}()<>=+\-*/.,:]')
COPY = 0.9  # skeleton ratio at or above this counts as "structure copied"


def skeleton(program: str) -> list[str]:
    out = []
    for t in TOKEN.findall(program or ""):
        if t.startswith('"'):
            out.append("STR")
        elif re.fullmatch(r"\$?[\d.]+", t):
            out.append("NUM")
        elif re.fullmatch(r"\w+", t):
            out.append(t if t in KEYWORDS else "ID")
        else:
            out.append(t)
    return out


def ratio(a: list[str], b: list[str]) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def analyse(rows: list[dict], train_by_about: dict[str, list[list[str]]], refs: dict[str, list[str]]) -> dict:
    reused, other = [], []
    for r in rows:
        a = about_line(r.get("program"))
        if r.get("program") and a in train_by_about:
            sk = skeleton(r["program"])
            best = max(ratio(sk, t) for t in train_by_about[a])
            reused.append({"id": r["id"], "trap": r["trap"], "correct": bool(r["safe_and_correct"]),
                           "skeleton_vs_training": round(best, 3), "skeleton_vs_reference": round(ratio(sk, refs[r["id"]]), 3)})
        else:
            other.append(r)
    copied = [x for x in reused if x["skeleton_vs_training"] >= COPY]
    closer = [x for x in reused if x["skeleton_vs_training"] > x["skeleton_vs_reference"]]
    return {"n": len(rows), "reuse_about": len(reused),
            "reuse_correct": sum(x["correct"] for x in reused),
            "no_reuse": len(other), "no_reuse_correct": sum(bool(r["safe_and_correct"]) for r in other),
            "structure_copied_ratio_ge_0.9": len(copied), "structure_copied_correct": sum(x["correct"] for x in copied),
            "closer_to_training_than_to_reference": len(closer),
            "median_skeleton_vs_training": sorted(x["skeleton_vs_training"] for x in reused)[len(reused) // 2] if reused else None,
            "median_skeleton_vs_reference": sorted(x["skeleton_vs_reference"] for x in reused)[len(reused) // 2] if reused else None,
            "examples_copied_and_wrong": [x["id"] for x in copied if not x["correct"]][:5],
            "examples_reuse_but_restructured": [x["id"] for x in reused if x["skeleton_vs_training"] < 0.6][:5],
            "all": reused}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, help="label=path.jsonl")
    ap.add_argument("--train", default="data/synthetic_v4")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    train_by_about: dict[str, list[list[str]]] = collections.defaultdict(list)
    seen = set()
    for s in ("train", "valid"):
        for l in Path(f"{args.train}/{s}.jsonl").read_text(encoding="utf-8").splitlines():
            prog = json.loads(l)["program"]
            if prog not in seen:  # several wordings share one program
                seen.add(prog)
                train_by_about[about_line(prog)].append(skeleton(prog))
    refs = {t.id: skeleton(t.program) for t in load_tasks()}
    result = {"split": "eval/benchmark (dev) only", "training_data": args.train, "copy_threshold": COPY,
              "method": "statement skeletons (names/strings/numbers replaced), difflib ratio", "runs": {}}
    for item in args.run:
        label, path = item.split("=", 1)
        rows = [r for r in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines()) if r["set"] == "benchmark"]
        result["runs"][label] = {"file": path, **analyse(rows, train_by_about, refs)}
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    for label, r in result["runs"].items():
        print(label, {k: v for k, v in r.items() if k not in ("all", "file")})


if __name__ == "__main__":
    main()
