"""Checker-in-the-loop repair: if a program fails to parse or fails the checker,
show the model the exact error and ask for a corrected program, up to N rounds.

Only the parser and checker are used as feedback (never the reference program or
scenario results), so this is what a deployed system could do.

Usage:
  uv run --group ml python -m eval.repair --adapter outputs/ft-coder1.5b-v0.2/epoch2 \
      --plain eval/results/<plain run>.jsonl --tasks-dir eval/benchmark --label v0.2 --rounds 3
Writes eval/results/repair-<label>-<tasks>-<date>.jsonl/.json. Plain (round 0) and repaired
results are stored side by side and must be reported separately.
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--model", default=BASE)
    ap.add_argument("--plain", required=True, help="saved plain-output jsonl for the same tasks (round 0)")
    ap.add_argument("--tasks-dir", default="eval/benchmark")
    ap.add_argument("--label", required=True)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--fewshot", type=int, default=0)
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()

    tasks = {t.id: t for t in load_tasks(ROOT / args.tasks_dir)}
    plain = {r["id"]: r for r in map(json.loads, open(args.plain, encoding="utf-8")) if r["id"] in tasks}
    assert len(plain) == len(tasks), f"plain file covers {len(plain)} of {len(tasks)} tasks"
    gen = Generator(args.model, args.adapter)
    state = {tid: {"history": [], "raw": plain[tid]["raw"], "rounds_used": 0} for tid in tasks}
    started = time.time()
    for rnd in range(1, args.rounds + 1):
        todo = []
        for tid, st in state.items():
            fb = checker_feedback(tasks[tid], extract_program(st["raw"]))
            if fb:
                st["history"].append((st["raw"], fb))
                todo.append(tid)
        print(f"round {rnd}: {len(todo)} programs need repair", flush=True)
        if not todo:
            break
        for i in range(0, len(todo), args.batch):
            chunk = todo[i:i + args.batch]
            prompts = [gen.prompt_text(repair_messages(tasks[t], state[t]["history"], bool(args.fewshot))) for t in chunk]
            for tid, raw in zip(chunk, gen.generate(prompts)):
                state[tid]["raw"] = raw
                state[tid]["rounds_used"] = rnd
    rows = []
    for tid, t in tasks.items():
        rep = score_row("benchmark", t, state[tid]["raw"], extract_program(state[tid]["raw"]))
        rows.append({"id": tid, "trap": t.trap, "rounds_used": state[tid]["rounds_used"],
                     "plain": {k: plain[tid][k] for k in ("parse", "check", "exec", "safe_and_correct")},
                     "repaired": {k: rep[k] for k in ("parse", "check", "exec", "safe_and_correct", "detail")},
                     "repaired_program": rep["program"], "monitor_problems": rep["monitor_problems"]})
    n = len(rows)
    traps = [r for r in rows if r["trap"] != "none"]

    def rate(sub, which, key):
        return round(sum(r[which][key] for r in sub) / len(sub), 4) if sub else None

    summary = {"label": args.label, "adapter": args.adapter, "tasks": args.tasks_dir, "n": n,
               "rounds_max": args.rounds, "date": date.today().isoformat(), "seconds": round(time.time() - started),
               "feedback": "parser + checker only",
               "plain": {k: rate(rows, "plain", k) for k in ("parse", "check", "exec", "safe_and_correct")},
               "repaired": {k: rate(rows, "repaired", k) for k in ("parse", "check", "exec", "safe_and_correct")},
               "plain_traps": rate(traps, "plain", "safe_and_correct"),
               "repaired_traps": rate(traps, "repaired", "safe_and_correct"),
               "monitor_problems_total": sum(len(r["monitor_problems"]) for r in rows)}
    base = RESULTS / f"repair-{args.label}-{Path(args.tasks_dir).name}-{summary['date']}"
    with open(f"{base}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    Path(f"{base}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
