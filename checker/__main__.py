"""Command line: check (and optionally render) Aether files.

    uv run python -m checker program.ae [policy.ae ...] [--render]

Exit code 0 if every procedure passes, 1 if any has errors, 2 on a syntax error.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .check import check
from .parser import AetherSyntaxError, parse_source
from .render import render


def main(argv: list[str]) -> int:
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print(__doc__)
        return 2
    policies, procedures = {}, {}
    for f in files:
        try:
            parsed = parse_source(Path(f).read_text(encoding="utf-8"))
        except AetherSyntaxError as exc:
            print(f"{f}: syntax error: {exc}")
            return 2
        policies.update(parsed.policies)
        procedures.update(parsed.procedures)
    status = 0
    for name, proc in procedures.items():
        pol = policies.get(proc.policy)
        if pol is None:
            print(f"{name}: policy {proc.policy} not found in the given files")
            status = 1
            continue
        diags = check(proc, pol)
        errs = [d for d in diags if d.is_error]
        print(f"{name}: {'FAIL' if errs else 'OK'} ({len(errs)} errors, {len(diags) - len(errs)} warnings)")
        for d in diags:
            print(f"  {d}")
        if errs:
            status = 1
        elif "--render" in argv:
            print(render(proc, pol))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
