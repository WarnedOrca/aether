"""Checker-in-the-loop repair: if a program fails to parse or fails the checker,
show the model the exact error and ask for a corrected program, up to N rounds.

Only the parser and checker are used as feedback (never the reference program or
scenario results), so this is what a deployed system could do.

Usage:
  uv run --group ml python -m eval.repair --adapter outputs/ft-coder1.5b-v0.2/epoch2 \
      --plain eval/results/<plain run>.jsonl --tasks-dir eval/benchmark --label v0.2 --rounds 3
Writes eval/results/repair-<label>-<tasks>-<date>.jsonl/.json (or --out <path without extension>). Plain (round 0)
and repaired results are stored side by side and must be reported separately.

Resumable: each task is repaired on its own (all its rounds), scored, and its row is saved before the next task starts.
Rerunning the same command (same --out) skips finished tasks; changed settings are refused. The summary .json is
written only when every task has a row.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

from checker.check import check
from checker.diagnostics import errors
from checker.parser import parse_source

from .baseline import RESULTS, Generator, score_row
from .bench import Task, load_tasks
from .prompt import ROOT, chat_messages, extract_program

BASE = "Qwen/Qwen2.5-Coder-1.5B-Instruct"


def checker_feedback(task: Task, program: str) -> str:
    """Empty string if the program parses and passes the checker, else the first problem."""
    try:
        parsed = parse_source(program)
        procs = list(parsed.procedures.values())
        if len(procs) != 1:
            return f"Expected exactly one procedure, found {len(procs)}."
        pol = parse_source(task.policy).policies
        policy = pol.get(procs[0].policy)
        if policy is None:
            return f"Unknown policy '{procs[0].policy}'. Use the policy name you were given."
        errs = errors(check(procs[0], policy))
        return "\n".join(str(e) for e in errs[:3])
    except Exception as exc:  # noqa: BLE001 - parse errors are the feedback
        return f"Syntax error: {str(exc).splitlines()[0][:300]}"


def repair_messages(task: Task, history: list[tuple[str, str]], fewshot: bool) -> list[dict]:
    msgs = chat_messages(task.policy, task.sheets, task.sop, fewshot=fewshot)
    for raw, feedback in history:
        msgs.append({"role": "assistant", "content": raw})
        msgs.append({"role": "user", "content": "The Aether checker rejected this program:\n" + feedback
                     + "\nWrite the full corrected procedure. Follow the policy and the safety rules."})
    return msgs


def repair_one(gen, task: Task, raw: str, rounds: int, fewshot: bool) -> tuple[str, int]:
    """Up to `rounds` feedback rounds for one task; returns the final raw output and the rounds used."""
    history: list[tuple[str, str]] = []
    used = 0
    for rnd in range(1, rounds + 1):
        fb = checker_feedback(task, extract_program(raw))
        if not fb:
            break
        history.append((raw, fb))
        raw = gen.generate([gen.prompt_text(repair_messages(task, history, fewshot))])[0]
        used = rnd
    return raw, used


def summarise(rows: list[dict], args, seconds: int) -> dict:
    traps = [r for r in rows if r["trap"] != "none"]

    def rate(sub, which, key):
        return round(sum(r[which][key] for r in sub) / len(sub), 4) if sub else None

    return {"label": args.label, "adapter": args.adapter, "model": args.model, "tasks": args.tasks_dir, "n": len(rows),
            "rounds_max": args.rounds, "date": date.today().isoformat(), "seconds": seconds,
            "feedback": "parser + checker only", "order": "one task at a time (all rounds), saved after each task",
            "plain": {k: rate(rows, "plain", k) for k in ("parse", "check", "exec", "safe_and_correct")},
            "repaired": {k: rate(rows, "repaired", k) for k in ("parse", "check", "exec", "safe_and_correct")},
            "plain_correct": sum(r["plain"]["safe_and_correct"] for r in rows),
            "repaired_correct": sum(r["repaired"]["safe_and_correct"] for r in rows),
            "plain_traps": rate(traps, "plain", "safe_and_correct"),
            "repaired_traps": rate(traps, "repaired", "safe_and_correct"),
            "monitor_problems_total": sum(len(r["monitor_problems"]) for r in rows)}


def run(args, make_generator=Generator) -> dict | None:
    """Returns the summary when every task is done (None if interrupted before that)."""
    from stages.common import JsonlCheckpoint, write_json

    tasks = {t.id: t for t in load_tasks(ROOT / args.tasks_dir)}
    plain = {r["id"]: r for r in map(json.loads, open(args.plain, encoding="utf-8")) if r["id"] in tasks}
    assert len(plain) == len(tasks), f"plain file covers {len(plain)} of {len(tasks)} tasks"
    base = Path(args.out) if args.out else RESULTS / f"repair-{args.label}-{Path(args.tasks_dir).name}-{date.today().isoformat()}"
    base.parent.mkdir(parents=True, exist_ok=True)
    config = {k: getattr(args, k) for k in ("adapter", "model", "plain", "tasks_dir", "label", "rounds", "fewshot")}
    cfg_path = Path(f"{base}.config.json")
    if cfg_path.exists() and json.loads(cfg_path.read_text(encoding="utf-8")) != config:
        raise ValueError(f"{cfg_path} holds different settings; choose another --out")
    write_json(cfg_path, config)
    ck = JsonlCheckpoint(Path(f"{base}.partial.jsonl"))
    todo = [tid for tid in tasks if tid not in ck.done]
    print(f"{len(tasks) - len(todo)} of {len(tasks)} tasks already done; {len(todo)} to go", flush=True)
    started = time.time()
    gen = make_generator(args.model, args.adapter) if todo else None
    for n, tid in enumerate(todo, 1):
        t = tasks[tid]
        raw, used = repair_one(gen, t, plain[tid]["raw"], args.rounds, bool(args.fewshot))
        rep = score_row("benchmark", t, raw, extract_program(raw))
        ck.add({"key": tid, "id": tid, "trap": t.trap, "rounds_used": used,
                "plain": {k: plain[tid][k] for k in ("parse", "check", "exec", "safe_and_correct")},
                "repaired": {k: rep[k] for k in ("parse", "check", "exec", "safe_and_correct", "detail")},
                "repaired_program": rep["program"], "repaired_raw": raw, "monitor_problems": rep["monitor_problems"]})
        print(f"task {n}/{len(todo)} {tid}: rounds {used}, correct {rep['safe_and_correct']}", flush=True)
    ck.close()
    rows = [r for r in ck.records if r["id"] in tasks]
    if len(rows) != len(tasks):
        return None
    order = list(tasks)
    rows.sort(key=lambda r: order.index(r["id"]))
    summary = summarise(rows, args, round(time.time() - started))
    with open(f"{base}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if k != "key"}) + "\n")
    Path(f"{base}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--model", default=BASE)
    ap.add_argument("--plain", required=True, help="saved plain-output jsonl for the same tasks (round 0)")
    ap.add_argument("--tasks-dir", default="eval/benchmark")
    ap.add_argument("--label", required=True)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--fewshot", type=int, default=0)
    ap.add_argument("--batch", type=int, default=1, help="accepted for older callers (stage 5); tasks are now repaired one at a time")
    ap.add_argument("--out", default="", help="output path without extension (fixed name, so a rerun on another day resumes)")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
