"""Dev-only failure diagnosis from SAVED outputs (CPU only, no model is run).

For each run on the 110 benchmark tasks: failures by stage / checker error code, trap vs non-trap, business type.
For every E401 failure (a sheet or column the policy does not allow), find out why:
  invented     - the column is not in the task's sheet at all (it cannot come from the request)
  sop_mentions - the column is in the sheet, the policy does not allow it, and the owner's request mentions it
                 (a read or a write; "mentions" is a plain word match of the column name, so synonyms are missed)
  unprompted   - the column is in the sheet, the policy does not allow it, and the request never mentions it
                 (the model added the read on its own, ignoring the policy's allow-list)
and whether the program still names the policy it was given. Never run this on a held-out set.

Usage: python -m eval.dev_failure_analysis --run label=path.jsonl [...] --out eval/results/dev-failure-diagnosis-<date>.json
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

from eval.bench import load_tasks
from eval.dev_report import about_line

E401 = re.compile(r"E401[^\n]*?(reads|writes) (\w+)\.(\w+)")


def load(path: str) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines()) if r["set"] == "benchmark"}


def stage(r: dict) -> str:
    """parse / Exxx (first checker code) / runtime / wrong-effect / correct."""
    if r["safe_and_correct"]:
        return "correct"
    if not r["parse"]:
        return "parse"
    if not r["check"]:
        m = re.search(r"\bE\d{3}\b", r.get("detail") or "")
        return m.group(0) if m else "checker-other"
    if not r.get("runs", True):
        return "runtime"
    return "wrong-effect"


def sheet_columns(sheets: str, sheet: str) -> set[str]:
    m = re.search(rf"sheet {sheet}\b[^{{]*\{{([^}}]*)\}}", sheets)
    return {c.split(":")[0].strip() for c in m.group(1).split(",")} if m else set()


def mentions(sop: str, col: str) -> bool:
    words = col.lower().replace("_", " ")
    return words in sop.lower() or col.lower() in sop.lower()


def policy_name(program: str) -> str | None:
    m = re.search(r"^\s*policy (\w+)\s*$", program or "", re.M)
    return m.group(1) if m else None


def e401_cause(task, row: dict) -> dict:
    m = E401.search(row.get("detail") or "")
    action, sheet, col = (m.group(1), m.group(2), m.group(3)) if m else ("?", "?", "?")
    given = re.search(r"policy (\w+)", task.policy).group(1)
    if col not in sheet_columns(task.sheets, sheet):
        cause = "invented"
    elif mentions(task.sop, col):
        cause = "sop_mentions"
    else:
        cause = "unprompted"
    return {"id": task.id, "action": action, "column": f"{sheet}.{col}", "cause": cause,
            "uses_given_policy": policy_name(row.get("program")) == given}


def analyse(rows: dict[str, dict], tasks: dict, train_about: set[str]) -> dict:
    fails = [r for r in rows.values() if not r["safe_and_correct"]]
    by_stage = collections.Counter(stage(r) for r in rows.values())
    by_trap = {"non_trap": collections.Counter(stage(r) for r in rows.values() if r["trap"] == "none"),
               "trap": collections.Counter(stage(r) for r in rows.values() if r["trap"] != "none")}
    biz_n = collections.Counter(tasks[i].business for i in rows)
    biz_fail = collections.Counter(tasks[r["id"]].business for r in fails)
    e401 = [e401_cause(tasks[r["id"]], r) for r in rows.values() if stage(r) == "E401"]
    for e in e401:
        e["memorised_about"] = about_line(rows[e["id"]].get("program")) in train_about
    causes = collections.Counter(e["cause"] for e in e401)
    actions = collections.Counter(e["action"] for e in e401)
    columns = collections.Counter(e["column"].split(".")[1] for e in e401)
    return {"n": len(rows), "correct": len(rows) - len(fails), "failures_by_stage": dict(by_stage.most_common()),
            "failures_by_stage_trap_vs_non_trap": {k: dict(v.most_common()) for k, v in by_trap.items()},
            "by_business": {b: {"n": biz_n[b], "failed": biz_fail[b]} for b in sorted(biz_n)},
            "e401": {"count": len(e401), "by_cause": dict(causes), "by_action": dict(actions), "top_columns": columns.most_common(6),
                     "uses_given_policy": sum(e["uses_given_policy"] for e in e401),
                     "memorised_about_line": sum(e["memorised_about"] for e in e401),
                     "examples_by_cause": {c: [e["id"] for e in e401 if e["cause"] == c][:5] for c in causes},
                     "all": e401}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, help="label=path.jsonl; the first one is the reference")
    ap.add_argument("--train", default="data/synthetic_v4")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    tasks = {t.id: t for t in load_tasks()}
    train_about = {about_line(json.loads(l)["program"]) for s in ("train", "valid")
                   for l in Path(f"{args.train}/{s}.jsonl").read_text(encoding="utf-8").splitlines()}
    runs = dict(item.split("=", 1) for item in args.run)
    data = {label: load(path) for label, path in runs.items()}
    result = {"split": "eval/benchmark (dev) only", "files": runs, "runs": {k: analyse(v, tasks, train_about) for k, v in data.items()}}
    ref_label = next(iter(data))
    ref = data[ref_label]
    for label, rows in list(data.items())[1:]:  # the same tasks: what does the reference do where this run hits E401?
        ids = [e["id"] for e in result["runs"][label]["e401"]["all"]]
        result["runs"][label]["e401"]["reference_on_same_tasks"] = {
            "reference": ref_label, "outcomes": dict(collections.Counter(stage(ref[i]) for i in ids)),
            "reference_correct_ids": [i for i in ids if ref[i]["safe_and_correct"]][:5],
            "trap_tasks": sum(rows[i]["trap"] != "none" for i in ids)}
    train_programs = [json.loads(l)["program"] for l in Path(f"{args.train}/train.jsonl").read_text(encoding="utf-8").splitlines()]
    cols = sorted({e["column"].split(".")[1] for r in result["runs"].values() for e in r["e401"]["all"]})
    result["training_programs_using_column"] = {  # base rate: how many training programs filter/where/set on each column
        "n": len(train_programs), "note": "programs with the column name in a filter/where/set line",
        "counts": {c: sum(bool(re.search(rf"(filter|where|set)[^
]*{c}", p)) for p in train_programs) for c in cols}}
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    for label, r in result["runs"].items():
        print(label, "correct", r["correct"], "| stages", r["failures_by_stage"])
        print("   E401", r["e401"]["count"], r["e401"]["by_cause"], "uses given policy", r["e401"]["uses_given_policy"],
              "memorised about", r["e401"]["memorised_about_line"], r["e401"].get("reference_on_same_tasks", ""))


if __name__ == "__main__":
    main()
