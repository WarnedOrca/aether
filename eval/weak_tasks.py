"""List benchmark tasks that a do-nothing program would pass (the scenarios never trigger an effect).

Usage: uv run python -m eval.weak_tasks
"""

from __future__ import annotations

import re

from .bench import Task, load_tasks, score


def noop_program(t: Task) -> str:
    trig = re.search(r"^\s*trigger .*$", t.program, re.MULTILINE).group(0)
    header = t.program[: t.program.index(trig) + len(trig)]
    return t.policy + "\n" + header + "\n  log \"noop\"\n}"


def weak_tasks(tasks: list[Task] | None = None) -> list[str]:
    return [t.id for t in (tasks or load_tasks()) if score(t, noop_program(t)).exec]


if __name__ == "__main__":
    weak = weak_tasks()
    print(len(weak), weak)
