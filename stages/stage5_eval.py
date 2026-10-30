"""Stage 5: run every pre-declared condition ONCE on frozen held-out v3, then write the declared report.

Conditions come from a JSON file written and committed BEFORE this runs (see stages/stage5_conditions.example.json);
the stage-4 model in it must be chosen on the dev split only. Each condition runs as its own subprocess with its own
log; a completed condition is never run again. A condition interrupted by a crash or shutdown resumes on rerun only
with the identical command and conditions file: each run saves every finished task and never regenerates it
(eval.baseline / eval.repair with --out). Anything else stops for owner review.
If the declared confirmatory comparison cannot be run (its model is not in the conditions), the conditions file sets
"confirmatory": null and no confirmatory test is computed; every condition is then reported as exploratory.

Declared metrics (vault decision log, 2026-10-25): non-trap success (36 tasks) and trap safe-alternative rate
(36 tasks), reported separately with 95% Wilson intervals, plus unsafe programs reaching execution (programs that
passed the checker and then caused a monitor problem;
read from each result's `monitor_problems_total`). Confirmatory: the chosen stage-4 model (plain) vs v0.2 plain,
exact McNemar on non-trap and on trap tasks, Holm-adjusted. Everything else is exploratory.

Usage (detached):
  .venv\\Scripts\\python.exe -m stages.stage5_eval --conditions stages/stage5_conditions.json
Writes eval/results/stage5/<name>.log, the result files, and eval/results/stage5/summary.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from eval.compare import mcnemar_exact, wilson
from stages.common import ROOT, check_license, get_logger, use_repo_hf_cache, write_json

TASKS = "eval/heldout3"
OUT = ROOT / "eval/results/stage5"


def result_file(c: dict) -> Path | None:
    pat = f"repair-{c['name']}-heldout3-*.jsonl" if c["kind"] == "repair" else (
        f"constrained-{c['name']}-heldout3-*.jsonl" if c["kind"] == "constrained" else f"baseline-*-heldout3-*-final3-{c['name']}.jsonl")
    hits = sorted((ROOT / "eval/results").glob(pat))
    return next((p for p in reversed(hits) if p.with_suffix(".json").is_file()), None)


def out_path(c: dict) -> Path:
    """Fixed output path (without extension) matching result_file's pattern, so a rerun continues the same files."""
    if c["kind"] == "plain":
        return ROOT / "eval/results" / f"baseline-{c['name']}-heldout3-run-final3-{c['name']}"
    return ROOT / "eval/results" / f"repair-{c['name']}-heldout3-run"


def may_resume(marker: Path, cmd: list[str], spec_hash: str) -> bool:
    """A started-but-unfinished condition may only continue with exactly the same command and conditions file."""
    if not marker.exists():
        return False
    prev = json.loads(marker.read_text(encoding="utf-8"))
    if prev.get("command") != cmd or prev.get("conditions_sha256") != spec_hash:
        raise ValueError(f"Interrupted condition {marker.stem} was started with a different command or conditions file; "
                         "stop for owner review")
    return True


def command(c: dict, conds: dict) -> list[str]:
    py = [sys.executable, "-u", "-m", "stages.gpu"]
    if c["kind"] == "plain":
        cmd = py + ["eval.baseline", "--model", c["model"], "--tasks-dir", TASKS, "--label", c["name"],
                    "--fewshot", str(c.get("fewshot", 0)), f"--suffix=-final3-{c['name']}", "--batch", str(c.get("batch", 4)), "--out", str(out_path(c))]
        return cmd + (["--adapter", c["adapter"]] if c.get("adapter") else [])
    if c["kind"] == "repair":
        plain = result_file(conds[c["plain_of"]])
        cmd = py + ["eval.repair", "--model", c["model"], "--tasks-dir", TASKS, "--label", c["name"], "--plain", str(plain),
                    "--batch", str(c.get("batch", 4)), "--out", str(out_path(c))]
        return cmd + (["--adapter", c["adapter"]] if c.get("adapter") else [])
    cmd = py + ["eval.constrained", "--tasks-dir", TASKS, "--label", c["name"]]
    return cmd + (["--adapter", c["adapter"]] if c.get("adapter") else [])


def load_rows(path: Path, kind: str) -> dict[str, dict]:
    out = {}
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        if kind == "repair":
            out[r["id"]] = {"ok": bool(r["repaired"]["safe_and_correct"]), "trap": r["trap"] != "none"}
        else:
            out[r["id"]] = {"ok": bool(r["safe_and_correct"]), "trap": r["trap"] != "none"}
    return out


def require_complete(path: Path, kind: str, expected: set[str]) -> None:
    if set(load_rows(path, kind)) != expected:
        raise ValueError("Incomplete result; owner review required before further evaluation")
    summary = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if not isinstance(summary.get("monitor_problems_total"), int):
        raise ValueError("Missing monitor evidence; owner review required")


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conditions", required=True)
    ap.add_argument("--condition-timeout", type=float, default=21600)
    args = ap.parse_args()
    use_repo_hf_cache()
    OUT.mkdir(parents=True, exist_ok=True)
    log = get_logger(OUT / "run.log")
    spec_path = ROOT / args.conditions
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    from eval.bench import load_tasks
    expected = {t.id for t in load_tasks(ROOT / TASKS)}
    if args.condition_timeout <= 0:
        ap.error("condition-timeout must be positive")
    if len({c["name"] for c in spec["conditions"]}) != len(spec["conditions"]):
        raise ValueError("Duplicate condition names")
    spec_hash = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    committed = subprocess.check_output(["git", "show", f"HEAD:{spec_path.relative_to(ROOT).as_posix()}"], cwd=ROOT)
    if committed != spec_path.read_bytes():
        raise ValueError("Commit the exact conditions file before stage 5")
    state_path = OUT / "conditions_sha256.json"
    if state_path.exists() and json.loads(state_path.read_text())["sha256"] != spec_hash:
        raise ValueError("Conditions changed after stage 5 started")
    write_json(state_path, {"sha256": spec_hash})
    for c in spec["conditions"]:
        check_license(c["model"], log)
    conds = {c["name"]: c for c in spec["conditions"]}
    conf = spec.get("confirmatory")
    a, b = (conf["new"], conf["baseline"]) if conf else (None, None)
    if conf and not {a, b} <= set(conds):
        raise ValueError("Confirmatory conditions must be in the conditions list")
    log.info("conditions file %s sha256 %s: %s; confirmatory %s vs %s", args.conditions, spec_hash, list(conds), a, b)
    for c in spec["conditions"]:
        if result_file(c):
            require_complete(result_file(c), c["kind"], expected)
            log.info("%s: result exists (%s); not running again", c["name"], result_file(c).name)
            continue
        marker = OUT / f"{c['name']}.started.json"
        env = {**os.environ, "AETHER_LOAD_4BIT": "1" if c.get("load_4bit") else "0", "PYTHONIOENCODING": "utf-8"}
        cmd = command(c, conds)
        if may_resume(marker, cmd, spec_hash):
            log.info("%s: resuming after an interruption (finished tasks are kept, never regenerated)", c["name"])
        else:
            log.info("%s: starting %s", c["name"], " ".join(cmd[3:]))
            write_json(marker, {"conditions_sha256": spec_hash, "command": cmd})
        t0 = time.time()
        with (OUT / f"{c['name']}.log").open("a", encoding="utf-8") as f:
            rc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT,
                                timeout=args.condition_timeout).returncode
        if rc != 0 or not result_file(c):
            log.error("%s failed (exit %d); see %s.log. Owner review required before any further execution.", c["name"], rc, c["name"])
            raise SystemExit(1)
        require_complete(result_file(c), c["kind"], expected)
        log.info("%s: done in %.0f s", c["name"], time.time() - t0)

    table, runs = {}, {}
    for name, c in conds.items():
        runs[name] = load_rows(result_file(c), c["kind"])
        rs = runs[name]
        nt = [r for r in rs.values() if not r["trap"]]
        tr = [r for r in rs.values() if r["trap"]]
        knt, ktr = sum(r["ok"] for r in nt), sum(r["ok"] for r in tr)
        table[name] = {"kind": c["kind"], "status": "confirmatory" if name in (a, b) else "exploratory",
                       "non_trap": {"correct": knt, "n": len(nt), "ci95": wilson(knt, len(nt))},
                       "trap": {"correct": ktr, "n": len(tr), "ci95": wilson(ktr, len(tr))},
                       "unsafe_programs_reaching_execution": json.loads(result_file(c).with_suffix(".json").read_text(
                           encoding="utf-8")).get("monitor_problems_total"),
                       "file": result_file(c).name}
    tests = {}
    for part, want in ((("non_trap", False), ("trap", True)) if conf else ()):
        ids = [i for i, r in runs[a].items() if r["trap"] == want and i in runs[b]]
        a_only = sum(runs[a][i]["ok"] and not runs[b][i]["ok"] for i in ids)
        b_only = sum(runs[b][i]["ok"] and not runs[a][i]["ok"] for i in ids)
        tests[part] = {"n": len(ids), "a_only": a_only, "b_only": b_only, "p": mcnemar_exact(a_only, b_only)}
    for part, p_adj in zip(tests, holm([t["p"] for t in tests.values()])):
        tests[part]["p_holm"] = p_adj
    summary = {"stage": 5, "finished": True, "tasks": TASKS, "conditions_file": args.conditions,
               "conditions_sha256": spec_hash,
               "confirmatory": {"new": a, "baseline": b, "tests": tests} if conf else None,
               "conditions": table,
               "note": ("Only the two confirmatory tests are pre-registered; everything else is exploratory." if conf else
                        "No confirmatory test: " + spec.get("_confirmatory_note", "none declared for these conditions")
                        + ". Every condition is exploratory.")}
    write_json(OUT / "summary.json", summary)
    log.info("done: %s", json.dumps(summary["confirmatory"]))


if __name__ == "__main__":
    main()
