"""Load the example programs straight from spec/SPEC.md section 10.

Keeping the spec as the single source of the examples means the tests fail
if the spec and the implementation drift apart.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import nodes as N
from .parser import parse_source

SPEC_PATH = Path(__file__).resolve().parent.parent / "spec" / "SPEC.md"
_FENCE = re.compile(r"```\n(.*?)```", re.DOTALL)


def example_section(spec_text: str) -> str:
    # Leading newline so "### 11. Auto repair" is not mistaken for "## 11."
    start = spec_text.index("\n## 10.")
    end = spec_text.index("\n## 11.")
    return spec_text[start:end]


def load_examples(path: Path = SPEC_PATH) -> N.SourceFile:
    """All policies and procedures defined in the examples section."""
    section = example_section(path.read_text(encoding="utf-8").replace("\r\n", "\n"))
    policies: dict[str, N.Policy] = {}
    procedures: dict[str, N.Procedure] = {}
    for block in _FENCE.findall(section):
        parsed = parse_source(block)
        policies.update(parsed.policies)
        procedures.update(parsed.procedures)
    return N.SourceFile(policies, procedures)
