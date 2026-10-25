"""Aether demo: check, explain, and run a business procedure in a sandbox.

Local:  uv run --group demo python demo/app.py      (opens http://127.0.0.1:7860)
Tab 1 needs no model and runs on CPU. Tab 2 (write with the model) needs the ml group and a GPU.
Everything runs against mock sheets; nothing is sent anywhere.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE if (HERE / "checker").exists() else HERE.parent  # Space folder vs. repo layout
sys.path.insert(0, str(ROOT))

import gradio as gr  # noqa: E402

from checker.check import check  # noqa: E402
from checker.mutate import block_defining  # noqa: E402
from checker.parser import AetherSyntaxError, parse_source  # noqa: E402
from checker.render import render  # noqa: E402
from interpreter.approvals import Always  # noqa: E402
from interpreter.sandbox import run_monitored, workspace_for  # noqa: E402

try:
    EXAMPLE = block_defining("AppointmentReminders")
except (FileNotFoundError, KeyError):  # Hugging Face Space: no spec folder, a flat example file instead
    EXAMPLE = (HERE / "example.ae").read_text(encoding="utf-8")
ADAPTER = ROOT / "outputs" / "ft-coder1.5b" / "epoch2"


def analyze(source: str, approve: bool, seed: int):
    try:
        parsed = parse_source(source)
    except AetherSyntaxError as exc:
        return f"Syntax error: {exc}", "", "", ""
    if len(parsed.procedures) != 1:
        return "Paste exactly one procedure (and its policy).", "", "", ""
    (proc,) = parsed.procedures.values()
    policy = parsed.policies.get(proc.policy)
    if policy is None:
        return f"Policy {proc.policy} not found. Paste the policy block too.", "", "", ""
    diags = sorted(check(proc, policy), key=lambda d: not d.is_error)  # errors first
    errors = [d for d in diags if d.is_error]
    verdict = ("REJECTED by the checker - this program will not run.\n" if errors else "Passes the checker.\n")
    verdict += "\n".join(str(d) for d in diags) or "No warnings."
    if errors:
        return verdict, "", "", ""
    english = render(proc, policy)
    ws = workspace_for(proc, rng=random.Random(int(seed)), rows=8)
    out = run_monitored(proc, policy, ws, Always("approve" if approve else "deny"), params={"days": 60})
    sent = [f"{e['channel']} to {e['to']}: {e['body']}" for e in ws.connector_log if e["kind"] == "deliver"]
    other = [f"{e['kind']}: {json.dumps({k: v for k, v in e.items() if k not in ('kind', 'at')})}"
             for e in ws.connector_log if e["kind"] in ("money", "notify", "book", "cancel", "append")]
    outbox = f"Run status: {out.result.status} {out.result.reason}\n\n" + ("\n".join(sent + other) or "(nothing sent)")
    if out.problems:
        outbox += "\n\nMONITOR PROBLEMS: " + "; ".join(out.problems)
    audit = "\n".join(json.dumps(a) for a in out.result.audit)
    return verdict, english, outbox, audit


_GEN = None


def write_with_model(policy: str, sheets: str, sop: str) -> str:
    global _GEN
    if not ADAPTER.exists():
        return "Fine-tuned adapter not found (outputs/ft-coder1.5b/epoch2)."
    try:
        if _GEN is None:
            from eval.baseline import Generator
            _GEN = Generator("Qwen/Qwen2.5-Coder-1.5B-Instruct", str(ADAPTER))
    except Exception as exc:  # noqa: BLE001 - shown to the user
        return f"Model unavailable here ({type(exc).__name__}: {exc}). Needs `uv sync --group ml` and a GPU."
    from eval.prompt import chat_messages, extract_program
    raw = _GEN.generate([_GEN.prompt_text(chat_messages(policy, sheets, sop, fewshot=False))])[0]
    return policy.strip() + "\n\n" + extract_program(raw)


with gr.Blocks(title="Aether") as demo:
    gr.Markdown("# Aether\nA small language for business procedures. A checker enforces the policy's rules before "
                "anything runs; everything here uses mock data.")
    with gr.Tab("Check, explain, run"):
        src = gr.Code(EXAMPLE, label="Policy + procedure", lines=24)
        with gr.Row():
            approve = gr.Checkbox(True, label="Owner approves messages")
            seed = gr.Number(1, label="Sample-data seed", precision=0)
            go = gr.Button("Check and run", variant="primary")
        verdict = gr.Textbox(label="Checker", lines=4)
        english = gr.Textbox(label="Plain-English rendering", lines=12)
        outbox = gr.Textbox(label="What happened (mock outbox and actions)", lines=8)
        audit = gr.Textbox(label="Audit log", lines=8)
        go.click(analyze, [src, approve, seed], [verdict, english, outbox, audit])
    with gr.Tab("Write with the model (GPU)"):
        pol = gr.Code(EXAMPLE.split("procedure")[0].strip(), label="Policy")
        sh = gr.Textbox('sheet Appointments "Appointments" { patient: Text, phone: Phone, starts: DateTime, status: Text, reason: Text private }', label="Sheets")
        sop = gr.Textbox("Every morning at 9, text patients with an appointment tomorrow. I approve each text.", label="SOP")
        gen = gr.Button("Write program")
        out_prog = gr.Code(label="Generated (paste into the first tab to check it)")
        gen.click(write_with_model, [pol, sh, sop], out_prog)

if __name__ == "__main__":
    demo.launch()
