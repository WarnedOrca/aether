"""Rescore saved model outputs under the current scorer and tasks (no regeneration).

Usage: uv run python -m eval.rescore eval/results/baseline-<model>-<date>.jsonl
Writes <same name>-rescored.json / .jsonl next to the input; the original files are kept.
Note: outputs keep the prompt they were generated with; only the scoring changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .baseline import score_row, summarize, synthetic_tasks
from .bench import load_tasks


def main(path: str) -> None:
    src = Path(path)
    tasks = {t.id: t for t in load_tasks()}
    tasks.update({t.id: t for t in synthetic_tasks(1000)})
    rows = [json.loads(line) for line in src.open(encoding="utf-8")]
    new = [score_row(r["set"], tasks[r["id"]], r["raw"], r["program"]) for r in rows]
    base = src.with_suffix("")
    with open(f"{base}-rescored.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in new:
            f.write(json.dumps(r) + "\n")
    old_meta = json.loads(Path(f"{base}.json").read_text(encoding="utf-8")) if Path(f"{base}.json").exists() else {}
    summary = {"rescored_from": src.name, "model": old_meta.get("model"), "generated": old_meta.get("date"),
               "note": "outputs generated with the pre-2026-10-25 SOP wording; scored with the split rule",
               **summarize(new)}
    Path(f"{base}-rescored.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    b = summary["benchmark"]
    print(f"{src.name}: benchmark exec={b['exec']} exec_blank={b['exec_blank']} exec_all={b['exec_all']} "
          f"safe_and_correct={b['safe_and_correct']}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
