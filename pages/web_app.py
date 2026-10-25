"""Browser entry point for the GitHub Pages demo (runs inside Pyodide).

Same flow as demo/app.py, without Gradio: check -> render -> run on mock data.
"""

from __future__ import annotations

import json
import random

from checker.check import check
from checker.parser import AetherSyntaxError, parse_source
from checker.render import render
from interpreter.approvals import Always
from interpreter.sandbox import run_monitored, workspace_for


def analyze(source: str, approve: bool, seed: int) -> str:
    out = {"verdict": "", "english": "", "outbox": "", "audit": ""}
    try:
        parsed = parse_source(source)
    except AetherSyntaxError as exc:
        out["verdict"] = f"Syntax error: {exc}"
        return json.dumps(out)
    if len(parsed.procedures) != 1:
        out["verdict"] = "Paste exactly one procedure (and its policy)."
        return json.dumps(out)
    (proc,) = parsed.procedures.values()
    policy = parsed.policies.get(proc.policy)
    if policy is None:
        out["verdict"] = f"Policy {proc.policy} not found. Paste the policy block too."
        return json.dumps(out)
    diags = sorted(check(proc, policy), key=lambda d: not d.is_error)
    errors = [d for d in diags if d.is_error]
    head = "REJECTED by the checker: this program will not run.\n" if errors else "Passes the checker.\n"
    out["verdict"] = head + ("\n".join(str(d) for d in diags) or "No warnings.")
    if errors:
        return json.dumps(out)
    out["english"] = render(proc, policy)
    ws = workspace_for(proc, rng=random.Random(int(seed)), rows=8)
    res = run_monitored(proc, policy, ws, Always("approve" if approve else "deny"), params={"days": 60})
    sent = [f"{e['channel']} to {e['to']}: {e['body']}" for e in ws.connector_log if e["kind"] == "deliver"]
    other = [f"{e['kind']}: " + json.dumps({k: v for k, v in e.items() if k not in ("kind", "at")})
             for e in ws.connector_log if e["kind"] in ("money", "notify", "book", "cancel", "append")]
    outbox = f"Run status: {res.result.status} {res.result.reason}\n\n" + ("\n".join(sent + other) or "(nothing sent)")
    if res.problems:
        outbox += "\n\nMONITOR PROBLEMS: " + "; ".join(res.problems)
    out["outbox"] = outbox
    out["audit"] = "\n".join(json.dumps(a) for a in res.result.audit)
    return json.dumps(out)
