"""Baseline: prompt a local open model (few-shot) and score it on the benchmark and synthetic test set.

Usage:
  uv run --group ml python -m eval.baseline --model Qwen/Qwen2.5-Coder-1.5B-Instruct [--limit 10]
Writes:
  eval/results/baseline-<model>-<date>.jsonl   one line per item: prompt id, raw output, program, scores
  eval/results/baseline-<model>-<date>.json    summary (the only source for METRICS.md numbers)
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import date
from pathlib import Path

from .bench import Task, load_tasks, score
from .prompt import ROOT, chat_messages, extract_program

RESULTS = ROOT / "eval" / "results"


def synthetic_tasks(n: int, seed: int = 0) -> list[Task]:
    rows = [json.loads(line) for line in (ROOT / "data/synthetic/test.jsonl").open(encoding="utf-8")]
    rng = random.Random(seed)
    rows = rng.sample(rows, min(n, len(rows)))
    return [Task(r["id"], r["domain"], r["pattern"], "none", r["sop"], r["policy"], r["program"],
                 {"days": "60"} if "requested(days" in r["program"] else {}) for r in rows]


class Generator:
    def __init__(self, model_id: str, adapter: str | None = None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_id)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.bfloat16, device_map="cuda")
        if adapter:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, adapter)
        self.model.eval()

    def prompt_text(self, messages: list[dict]) -> str:
        kwargs = {"tokenize": False, "add_generation_prompt": True}
        try:
            return self.tok.apply_chat_template(messages, enable_thinking=False, **kwargs)
        except TypeError:
            return self.tok.apply_chat_template(messages, **kwargs)

    def generate(self, prompts: list[str], max_new_tokens: int = 700) -> list[str]:
        enc = self.tok(prompts, return_tensors="pt", padding=True).to("cuda")
        with self.torch.no_grad():
            out = self.model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                                      pad_token_id=self.tok.pad_token_id)
        new = out[:, enc["input_ids"].shape[1]:]
        return self.tok.batch_decode(new, skip_special_tokens=True)


def summarize(rows: list[dict]) -> dict:
    def rate(key, subset):
        return round(sum(r[key] for r in subset) / len(subset), 4) if subset else None

    out = {}
    for name, subset in (("benchmark", [r for r in rows if r["set"] == "benchmark"]),
                         ("benchmark_traps", [r for r in rows if r["set"] == "benchmark" and r["trap"] != "none"]),
                         ("benchmark_non_traps", [r for r in rows if r["set"] == "benchmark" and r["trap"] == "none"]),
                         ("synthetic_test", [r for r in rows if r["set"] == "synthetic"])):
        out[name] = {"n": len(subset), **{k: rate(k, subset) for k in
                                          ("parse", "check", "runs", "exec", "exec_blank", "exec_all", "safe_and_correct")}}
    return out


def score_row(which: str, t: Task, raw: str, program: str) -> dict:
    s = score(t, program)
    return {"set": which, "id": t.id, "trap": t.trap, "category": t.category, "raw": raw, "program": program,
            "parse": s.parse, "check": s.check, "runs": s.runs, "exec": s.exec, "exec_blank": s.exec_blank,
            "exec_all": s.exec_all, "safe_and_correct": s.safe_and_correct, "detail": s.detail,
            "monitor_problems": s.monitor_problems}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", default=None, help="LoRA adapter directory (fine-tuned model)")
    ap.add_argument("--fewshot", type=int, default=1, help="1 = include 3 worked examples, 0 = none")
    ap.add_argument("--limit", type=int, default=0, help="only the first N items of each set (smoke test)")
    ap.add_argument("--synthetic", type=int, default=100)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--suffix", default="", help="appended to output file names, e.g. -v2")
    ap.add_argument("--tasks-dir", default="", help="score on another task folder (e.g. eval/heldout); skips synthetic")
    ap.add_argument("--label", default="", help="file label for the model, e.g. v0.1")
    args = ap.parse_args()

    if args.tasks_dir:
        items = [("benchmark", t) for t in load_tasks(ROOT / args.tasks_dir)]
    else:
        items = [("benchmark", t) for t in load_tasks()] + [("synthetic", t) for t in synthetic_tasks(args.synthetic)]
    if args.limit:
        items = [x for x in items if x[0] == "benchmark"][: args.limit] + [x for x in items if x[0] == "synthetic"][: args.limit]
    gen = Generator(args.model, args.adapter)
    tag = (args.model.split("/")[-1] + ("-ft" if args.adapter else "") + (f"-{args.label}" if args.label else "")
           + ("" if args.fewshot else "-zeroshot") + ("-" + Path(args.tasks_dir).name if args.tasks_dir else ""))
    stamp = date.today().isoformat()
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    started = time.time()
    for i in range(0, len(items), args.batch):
        chunk = items[i:i + args.batch]
        prompts = [gen.prompt_text(chat_messages(t.policy, t.sheets, t.sop, fewshot=bool(args.fewshot))) for _, t in chunk]
        outputs = gen.generate(prompts)
        for (which, t), raw in zip(chunk, outputs):
            rows.append(score_row(which, t, raw, extract_program(raw)))
        print(f"{len(rows)}/{len(items)} done, {time.time() - started:.0f}s", flush=True)
    base = RESULTS / f"baseline-{tag}-{stamp}{args.suffix}{'-smoke' if args.limit else ''}"
    with open(f"{base}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    summary = {"model": args.model, "adapter": args.adapter, "fewshot": bool(args.fewshot), "date": stamp,
               "tasks": args.tasks_dir or "eval/benchmark + synthetic test",
               "batch": args.batch, "scoring": "exec = blank-free scenarios (2026-10-25 rule)",
               "decoding": "greedy, max_new_tokens=700", "seconds": round(time.time() - started),
               "monitor_problems_total": sum(len(r["monitor_problems"]) for r in rows), **summarize(rows)}
    Path(f"{base}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
