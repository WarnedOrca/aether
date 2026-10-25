"""Checker diagnostics with stable codes (SPEC.md section 7)."""

from __future__ import annotations

from dataclasses import dataclass

MESSAGES = {
    "E101": "send used on an unapproved draft",
    "E102": "order or refund needs 'ask owner first'",
    "E103": "single approval inside a loop while the policy is in batch mode",
    "E104": "batch form used while the policy is in per_message mode",
    "E201": "cannot prove amount is within the per-action limit",
    "E202": "worst-case money per run exceeds the daily limit",
    "E301": "private data flows into a message",
    "E302": "recipient not from an allowed contact column",
    "E303": "supplier not from an allowed supplier source",
    "E401": "sheet or column not allowed by the policy",
    "E402": "calendar not allowed by the policy",
    "E501": "loop without bound, or wait longer than 30 days",
    "E502": "skip used outside a loop",
    "E601": "type or name error",
    "E701": "policy missing a required hard cap",
    "E702": "policy threshold order broken",
    "E703": "batch settings missing or out of bounds",
    "E704": "unknown or weakening policy rule",
    "W101": "column interpolated without a default; a blank cell blocks the message",
    "W201": "cap above the reference value (large cap)",
}


@dataclass(frozen=True)
class Diagnostic:
    code: str
    detail: str
    line: int = 0

    @property
    def is_error(self) -> bool:
        return self.code.startswith("E")

    def __str__(self) -> str:
        where = f"line {self.line}: " if self.line else ""
        return f"{where}{self.code} {MESSAGES.get(self.code, '')}: {self.detail}"


def errors(diags: list[Diagnostic]) -> list[Diagnostic]:
    return [d for d in diags if d.is_error]


def codes(diags: list[Diagnostic]) -> set[str]:
    return {d.code for d in diags}
