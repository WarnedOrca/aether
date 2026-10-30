"""Descriptive report of the finished stage 5 run (held-out v3), computed only from its committed result files.

Adds what eval/results/stage5/summary.json does not list: correct out of all 72 tasks with a 95% Wilson interval, parse
and checker-pass rates, how many programs the checker blocked (parsed but rejected), and monitor problems. It runs no
model and adds no comparison or test (none was declared for these conditions).

Usage: python -m eval.stage5_report  ->  eval/results/stage5/report.json
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.compare import wilson
from stages.common import ROOT, write_json

OUT = ROOT / "eval/results/stage5"


def main() -> None:
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    report = {"source": "eval/results/stage5/summary.json and the result files it names", "tasks": summary["tasks"],
              "conditions_sha256": summary["conditions_sha256"], "confirmatory": summary["confirmatory"],
              "note": summary["note"], "conditions": {}}
    for name, c in summary["conditions"].items():
        path = ROOT / "eval/results" / c["file"]
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        res = (lambda r: r["repaired"]) if c["kind"] == "repair" else (lambda r: r)
        n = len(rows)
        ok = sum(bool(res(r)["safe_and_correct"]) for r in rows)
        parsed = sum(bool(res(r)["parse"]) for r in rows)
        passed = sum(bool(res(r)["check"]) for r in rows)
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        report["conditions"][name] = {
            "kind": c["kind"], "status": c["status"], "n": n, "correct": ok, "ci95": wilson(ok, n),
            "non_trap": c["non_trap"], "trap": c["trap"],
            "parse_rate": round(parsed / n, 4), "checker_pass_rate": round(passed / n, 4),
            "blocked_by_checker": parsed - passed,
            "monitor_problems_total": meta.get("monitor_problems_total"),
            "unsafe_programs_reaching_execution": c["unsafe_programs_reaching_execution"]}
    write_json(OUT / "report.json", report)
    for name, r in report["conditions"].items():
        print(f"{name}: {r['correct']}/{r['n']} {r['ci95']} non-trap {r['non_trap']['correct']}/{r['non_trap']['n']} "
              f"trap {r['trap']['correct']}/{r['trap']['n']} parse {r['parse_rate']} check {r['checker_pass_rate']} "
              f"blocked {r['blocked_by_checker']} monitor {r['monitor_problems_total']}")


if __name__ == "__main__":
    main()
