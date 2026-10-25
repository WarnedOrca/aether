"""Validate benchmark tasks: every reference must parse, pass the checker, run, and score itself perfectly.

Usage: uv run python -m eval.check_benchmark
"""

from __future__ import annotations

from collections import Counter

from .bench import load_tasks, score


def main() -> None:
    tasks = load_tasks()
    bad = 0
    ids = Counter(t.id for t in tasks)
    for t in tasks:
        if ids[t.id] > 1:
            print(f"DUPLICATE id {t.id}")
            bad += 1
        try:
            s = score(t, t.policy + "\n" + t.program)
        except Exception as exc:  # noqa: BLE001
            print(f"{t.id}: EXCEPTION {type(exc).__name__}: {exc}")
            bad += 1
            continue
        if not s.safe_and_correct or s.monitor_problems:
            print(f"{t.id}: FAIL {s.detail} {s.monitor_problems[:2]}")
            bad += 1
    print(f"{len(tasks)} tasks, {len(tasks) - bad} valid, traps={sum(t.trap != 'none' for t in tasks)}, "
          f"categories={len(set(t.category for t in tasks))}")


if __name__ == "__main__":
    main()
