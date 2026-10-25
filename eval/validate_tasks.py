"""Validate a task folder: references score perfectly, no weak tasks, unique ids.

Usage: uv run python -m eval.validate_tasks eval/heldout2
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from .bench import load_tasks, score
from .weak_tasks import noop_program


def main(folder: str) -> None:
    tasks = load_tasks(Path(folder))
    ids = Counter(t.id for t in tasks)
    bad = [i for i, c in ids.items() if c > 1]
    for t in tasks:
        try:
            s = score(t, t.policy + "\n" + t.program)
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{t.id}: {type(exc).__name__} {exc}")
            continue
        if not s.safe_and_correct or s.monitor_problems:
            bad.append(f"{t.id}: {s.detail} {s.monitor_problems[:1]}")
        elif score(t, noop_program(t)).exec:
            bad.append(f"{t.id}: weak (do-nothing program passes)")
    traps = sum(t.trap != "none" for t in tasks)
    print(f"{len(tasks)} tasks, {traps} traps, {len({t.business for t in tasks})} businesses; problems: {len(bad)}")
    for b in bad:
        print("  ", b)


if __name__ == "__main__":
    main(sys.argv[1])
