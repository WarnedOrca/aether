"""Dev-only: how often does a model program reuse a training program's about line / logic body? Writes eval/results/dev-replay-check-2026-10-26.json."""
import json, re, sys
sys.stdout.reconfigure(encoding="utf-8")
def load(p): return [json.loads(l) for l in open(p, encoding="utf-8")]
def about(p):
    m = re.search(r'about "([^"]*)"', p); return m.group(1) if m else None
def body(p):
    i = p.find("let "); return re.sub(r"\s+", " ", p[i:]) if i >= 0 else ""
v4 = load("data/synthetic_v4/train.jsonl")
old = []
for d in ("data/synthetic", "data/synthetic_traps", "data/synthetic_v3"): old += load(d + "/train.jsonl")
A4 = {about(r["program"]) for r in v4}; AO = {about(r["program"]) for r in old}
B4 = {body(r["program"]) for r in v4}; BO = {body(r["program"]) for r in old}
tasks_about = {}
runs = {"new epoch2": "eval/results/baseline-Qwen2.5-Coder-7B-Instruct-ft-q7b-v1-epoch2-zeroshot-benchmark-2026-10-26-dev.jsonl",
        "v0.2": "eval/results/baseline-Qwen2.5-Coder-1.5B-Instruct-ft-v0.2-zeroshot-2026-10-25-final.jsonl"}
from eval.bench import load_tasks
ref = {t.id: t.program for t in load_tasks()}
res = {}
for n, p in runs.items():
    rows = [r for r in load(p) if r["set"] == "benchmark" and r.get("program")]
    a4 = sum(about(r["program"]) in A4 for r in rows); ao = sum(about(r["program"]) in AO for r in rows)
    b4 = sum(body(r["program"]) in B4 for r in rows); bo = sum(body(r["program"]) in BO for r in rows)
    # of the wrong-effect failures (checker passes, not correct): how many replay a training about / body?
    wrong = [r for r in rows if r["check"] and not r["safe_and_correct"]]
    wa = sum(about(r["program"]) in (A4 | AO) for r in wrong); wb = sum(body(r["program"]) in (B4 | BO) for r in wrong)
    ra = sum(about(r["program"]) == about(ref[r["id"]]) for r in rows)
    res[n] = dict(n=len(rows), about_in_v4_train=a4, about_in_any_train=ao, body_in_v4_train=b4, body_in_any_train=bo,
                  checker_passed_but_wrong=len(wrong), wrong_about_replayed=wa, wrong_body_replayed=wb)
    print(n, res[n])
json.dump(res, open("eval/results/dev-replay-check-2026-10-26.json", "w", encoding="utf-8"), indent=2)
