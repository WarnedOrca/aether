"""Text-level mutations of spec examples, used by negative tests and the benchmark."""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import nodes as N
from .check import check
from .diagnostics import Diagnostic
from .parser import parse_source
from .spec_examples import SPEC_PATH, _FENCE, example_section, load_examples


def example_blocks() -> list[str]:
    text = SPEC_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    return _FENCE.findall(example_section(text))


def block_defining(name: str) -> str:
    for block in example_blocks():
        if f"procedure {name} " in block or f"policy {name} " in block:
            return block
    raise KeyError(name)


def check_text(src: str, proc_name: str, policy_text: str | None = None) -> list[Diagnostic]:
    """Parse `src`; take the policy from `policy_text`, else `src`, else the spec."""
    parsed = parse_source(src)
    proc: N.Procedure = parsed.procedures[proc_name]
    policies = dict(load_examples().policies)
    policies.update(parsed.policies)
    if policy_text is not None:
        policies.update(parse_source(policy_text).policies)
    return check(proc, policies[proc.policy])


@dataclass(frozen=True)
class Mutant:
    procedure: str
    operator: str
    expected: str  # error code the checker must report
    source: str


_APPROVE = re.compile(r"let (\w+) = request (?:batch )?approval of (\w+)")
_LOOP_BOUND = re.compile(r"(for each \w+ in \w+) up to \d+")
_ASK = re.compile(r", ask owner first timeout [^\n]*?else (?:skip|stop \"[^\"]*\")")
_RECIPIENT = re.compile(r"(draft (?:each \w+ in \w+ up to \d+ )?(?:sms|email) to )(\w+\.\w+)")
_AMOUNT_REFUND = re.compile(r"^\s*refund (\S+) for ", re.MULTILINE)
_AMOUNT_ORDER = re.compile(r"^\s*order \"[^\"]*\" from \S+ cost (\S+?)(,|\n)", re.MULTILINE)
_DRAFT_BODY = re.compile(r"(draft (?:sms|email) to (\w+)\.\w+[^\n]*?:\s*\")")


def mutants(name: str) -> list[Mutant]:
    """Single-mutation variants of one spec example, each breaking one core rule."""
    src = block_defining(name)
    proc_at = src.index(f"procedure {name} ")
    head, body = src[:proc_at], src[proc_at:]
    out: list[Mutant] = []

    def add(op: str, code: str, new_body: str | None = None, new_head: str | None = None):
        new = (new_head if new_head is not None else head) + (new_body if new_body is not None else body)
        if new != src:
            out.append(Mutant(name, op, code, new))

    for m in _APPROVE.finditer(body):  # M1 send the draft instead of the approval
        add("delete_approval", "E101", body.replace(f"send {m.group(1)}\n", f"send {m.group(2)}\n"))
    for m in _LOOP_BOUND.finditer(body):  # M2 remove a loop bound
        add("remove_loop_bound", "E501", body.replace(m.group(0), m.group(1), 1))
    for m in _ASK.finditer(body):  # M3 remove an owner approval on money
        add("remove_money_approval", "E102", body.replace(m.group(0), "", 1))
    for m in _RECIPIENT.finditer(body):  # M4 literal recipient
        lit = '"+15550000000"' if " sms " in m.group(1) + " " else '"someone@example.com"'
        add("literal_recipient", "E302", body.replace(m.group(0), m.group(1) + lit, 1))
    for m in list(_AMOUNT_REFUND.finditer(body)) + list(_AMOUNT_ORDER.finditer(body)):  # M5 huge amount
        add("raise_amount", "E201", body[:m.start(1)] + "$100000.00" + body[m.end(1):])
    policy = load_examples().policies[load_examples().procedures[name].policy]
    privates = [r.args[0] for r in policy.rules if r.kind == "deny_reveal"]
    proc = load_examples().procedures[name]
    for m in _DRAFT_BODY.finditer(body):  # M6 leak a private column into a message
        row = m.group(2)
        for sheet, col in privates:
            if sheet in proc.sheets and col in proc.sheets[sheet].columns:
                add("leak_private", "E301", body.replace(m.group(1), m.group(1) + "{" + f"{row}.{col}" + "} ", 1))
                break
    if not head:  # the policy lives in another block; prepend a mutated copy of it
        head = block_defining(proc.policy).split("procedure ")[0]
    for line in head.splitlines():  # M7 drop a required cap
        if re.match(r"\s*limit (refund|order|sends) ", line):
            op = line.split()[1]
            used = {"refund": "refund ", "order": "order ", "sends": "send "}[op]
            if used in body:
                add("drop_cap", "E701", body, head.replace(line + "\n", "", 1))
    add("weakening_rule", "E704", body, head.replace("{\n", "{\n  allow send without approval\n", 1))
    return out


def run_mutants(names: list[str] | None = None) -> list[dict]:
    """Check every mutant; record whether it was rejected and with which codes."""
    rows = []
    for name in names or sorted(load_examples().procedures):
        for mu in mutants(name):
            try:
                found = {d.code for d in check_text(mu.source, mu.procedure) if d.is_error}
                parsed = True
            except Exception as exc:  # a parse failure also rejects the mutant
                found, parsed = {f"PARSE:{type(exc).__name__}"}, False
            rows.append({"procedure": mu.procedure, "operator": mu.operator, "expected": mu.expected,
                         "rejected": bool(found), "expected_found": mu.expected in found,
                         "parsed": parsed, "codes": sorted(found)})
    return rows


def mutate(name: str, old: str, new: str, count: int = 1) -> str:
    block = block_defining(name)
    if old not in block:
        raise ValueError(f"mutation target not found in {name}: {old!r}")
    return block.replace(old, new, count)
