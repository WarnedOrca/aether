"""One-time edit (2026-10-25): state blank-cell behavior in benchmark SOPs.

For every message in a task's reference program, the SOP gets one sentence
saying which sheet details the message uses, which blank details get a fallback,
and which blank details mean "don't send". Idempotent: tasks that already contain
"Blank cells:" are left alone.

Usage: uv run python -m eval.annotate_blanks
"""

from __future__ import annotations

import re

from checker import nodes as N
from checker.parser import parse_source

from .bench import BENCH_DIR, load_tasks

MARK = "Blank cells:"


def _col(e) -> str | None:
    if isinstance(e, N.Attr):
        return e.attr
    if isinstance(e, N.Call):
        for a in e.args:
            c = _col(a)
            if c:
                return c
    return None


def _walk(x):
    yield x
    if isinstance(x, (tuple, list)):
        for y in x:
            yield from _walk(y)
    elif hasattr(x, "__dataclass_fields__"):
        for f in x.__dataclass_fields__:
            yield from _walk(getattr(x, f))


def blank_sentence(program_and_policy: str) -> str:
    (proc,) = parse_source(program_and_policy).procedures.values()
    fallback: dict[str, str] = {}
    required: list[str] = []
    for node in _walk(proc.body):
        if not isinstance(node, N.Message):
            continue
        for s in (node.subject, node.body):
            if s is None:
                continue
            for p in s.parts:
                if not isinstance(p, N.Interp):
                    continue
                col = _col(p.expr)
                if col is None:
                    continue
                if p.default is not None:
                    fallback.setdefault(col, p.default)
                elif col not in required:
                    required.append(col)
    if not fallback and not required:
        return ""
    human = lambda c: c.replace("_", " ")  # noqa: E731
    used = list(dict.fromkeys(list(fallback) + required))
    parts = [f"{MARK} the message uses the {', '.join(human(c) for c in used)}"]
    for col, d in fallback.items():
        parts.append(f"if the {human(col)} is blank, write \"{d}\" instead" if d else
                     f"if the {human(col)} is blank, just leave it out")
    if required:
        parts.append(f"if the {' or '.join(human(c) for c in required)} is blank, don't send that message")
    return "; ".join(parts) + "."


def main() -> None:
    tasks = {t.id: t for t in load_tasks()}
    changed = 0
    for path in sorted(BENCH_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")

        def fix(m: re.Match) -> str:
            nonlocal changed
            head, tid, sop = m.group(1), m.group(2), m.group(3)
            if MARK in sop:
                return m.group(0)
            t = tasks[tid]
            sentence = blank_sentence(t.policy + "\n" + t.program)
            if not sentence:
                return m.group(0)
            changed += 1
            return f"{head}{sop.rstrip()} {sentence}\n"

        pattern = r"(?m)(^=== (\S+)\n(?:.*\n)*?--- sop\n)((?:(?!--- ).*\n)+)"
        path.write_text(re.sub(pattern, fix, text), encoding="utf-8", newline="\n")
    print(f"annotated {changed} SOPs")


if __name__ == "__main__":
    main()
