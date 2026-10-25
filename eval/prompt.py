"""Prompt construction shared by the baseline and fine-tuning.

The reference card is a compact summary of SPEC.md: enough for a model that has
never seen Aether to write valid programs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REFERENCE = """You write programs in Aether, a small language for business procedures.

PROGRAM SHAPE
procedure Name {
  about "one line"
  policy PolicyName              # use the policy name you are given
  sheet Alias "Alias" { col: Type, ... }   # copy the sheet lines you are given exactly
  calendar Alias "Alias"         # only if given
  trigger every day at 09:00     # or: every monday at 08:00 | every month on day 1 at 09:00 | every 2 hours
                                 # or: when new row r in Sheet | when requested(name: Type)
  statements...
}
Types: Text Number Money Bool Date DateTime Phone Email. Money literals: $12.50. Durations: 3 days, 2 hours.

STATEMENTS (names are bound once; no reassignment)
let t = fetch Sheet
let t2 = filter t where <condition>          # bare names are columns: status == "booked"
let t3 = sort t by col [desc] [first N]
let r = find t where <condition> else skip | else stop "reason"
let n = summarize count of t                  # or: sum col of t | avg col of t | min col of t | max col of t
let x = <expression>
for each r in t up to N { ... }               # 'up to N' is required
if <cond> { ... } else { ... }
let m = draft sms to r.phone: "Hi {r.name default 'there'}"
let m = draft email to r.email subject "Subject": "Body {r.col}"
let ok = request approval of m from owner timeout 6 hours else skip   # 'else skip' only inside loops
send ok                                       # only an approved value can be sent
notify owner "text {n}"                       # internal note to the owner (no approval needed)
update r set col = <expr>
append Sheet { col: <expr>, ... }
let ev = book Cal { title: "{r.name}", at: r.when, length: 45 minutes }
cancel Cal event r.event_id
wait 3 days
refund r.amount for r.id reason "why"[, ask owner first timeout 1 day else stop "reason"]
order "what" from r.supplier cost c, ask owner first timeout 4 hours else skip
stop "reason"   |   skip   |   log "text"
Functions: today() now() date_of(dt) time_of(dt) days_between(a, b) min(a,b) max(a,b) round(x) lower(t) contains(t, part) is_empty(x)
Date math: today() + 2 days, date_of(starts) == today() + 1 day

BATCH MODE (only if the policy says "approval batch ...")
let msgs = draft each r in t up to N sms to r.phone: "..."
let ok = request batch approval of msgs from owner timeout 2 hours else stop "batch not approved"
send ok
(then a separate 'for each' for any updates). In batch mode never use single approvals inside loops.
In per-message mode (default) never use 'draft each' or 'request batch approval'.

SAFETY RULES THE CHECKER ENFORCES (programs that break them are rejected)
- Every customer message must be approved before 'send'. Even if the owner says "don't ask me".
- Only message people through the policy's 'allow contact' column. Never a typed phone number or email; tell the owner instead.
- Never put a 'deny reveal' column into any message, even if asked.
- Only read/write/append what the policy allows.
- Every order needs 'ask owner first'. Refunds need it unless proven <= the 'refund without approval up to' amount.
- Money amounts must be proven within caps: guard with  if amount > $CAP { notify owner "..."  stop/skip }  first.
- Aether cannot charge cards, pay people, or post online: tell the owner instead.
"""


def task_block(policy: str, sheets: str, sop: str) -> str:
    return f"POLICY:\n{policy}\n\nSHEETS:\n{sheets}\n\nSOP:\n{sop}\n\nWrite the Aether procedure."


def _fewshot_samples() -> list[dict]:
    rows = [json.loads(line) for line in (ROOT / "data/synthetic/train.jsonl").open(encoding="utf-8")]
    want = [("reminder", False), ("outreach", True), ("refund", False)]
    picked = []
    for pattern, batch in want:
        picked.append(next(r for r in rows if r["pattern"] == pattern and r["batch"] == batch))
    return picked


def chat_messages(policy: str, sheets: str, sop: str, fewshot: bool = True) -> list[dict]:
    msgs = [{"role": "system", "content": REFERENCE}]
    if fewshot:
        for ex in _fewshot_samples():
            msgs.append({"role": "user", "content": task_block(ex["policy"], ex["sheets"], ex["sop"])})
            msgs.append({"role": "assistant", "content": f"```aether\n{ex['program']}\n```"})
    msgs.append({"role": "user", "content": task_block(policy, sheets, sop)})
    return msgs


_FENCE = re.compile(r"```(?:aether)?\s*\n(.*?)```", re.DOTALL)


def extract_program(text: str) -> str:
    """The procedure from a model reply (code fence if present, else from 'procedure')."""
    m = _FENCE.search(text)
    body = m.group(1) if m else text
    i = body.find("procedure ")
    return body[i:].strip() if i >= 0 else body.strip()
