"""Stage 3: many natural English wordings per fixed, verified program, written by a LOCAL open-weight model.

Provenance rule: the local model sees only the program, policy and sheet list (code made by the script
generator), never the generator's English SOP text, and no text from Claude, OpenAI or any hosted AI is used.
Every kept example records its source model, revision, licence, seed program and generation settings.

Kept only if: the program still parses, passes the checker and runs clean under the monitor (data.generate.verify);
the wording has no code, mentions every number the program depends on, is 12-140 words, is not a near-duplicate of
another wording of the same program, and does not overlap any evaluation set (benchmark, held-out v1/v2/v3).

Resumable: records go to <out>/records.jsonl as they are made; a restart skips finished keys.
Usage (Codex/PowerShell, detached):
  .venv\\Scripts\\python.exe -m stages.stage3_paraphrase --out data/synthetic_v4 --per-program 4
Writes <out>/train.jsonl, valid.jsonl, summary.json, log.txt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import time
from pathlib import Path

from stages.common import ROOT, model_load_kwargs, JsonlCheckpoint, check_license, get_logger, model_revision, use_repo_hf_cache, write_json

PROMPT_VERSION = "p1"
TRAP_HINTS = {  # the owner's request must contain the unsafe or impossible ask; the program is the safe answer
    "reveal-private": "The owner also asks to include the private field in the message.",
    "skip-approval": "The owner says not to bother asking for approval before sending.",
    "order-skip-approval": "The owner says to place the orders without asking first.",
    "over-limit": "The owner asks to order regardless of the total cost.",
    "raise-limit": "The owner asks to temporarily allow a bigger amount than the program's cap.",
    "unlisted-recipient": "The owner also asks to message an extra person whose address is not in the sheet.",
    "send-on-timeout": "The owner says to send anyway if they have not approved in time.",
    "unbounded": "The owner says to send to everyone with no limit.",
    "unsupported-channel": "The owner asks for a channel the program cannot use (a phone call or a social media post).",
    "unsupported-charge": "The owner asks to charge customers' cards automatically.",
    "unsupported-payment": "The owner asks to pay people automatically.",
    "delete-data": "The owner asks to delete the rows.",
}
CODE = re.compile(r"procedure |policy \w+ \{|let \w+ =|\{[a-z_]+\.|```|fetch |summarize ")


def load_seeds(sources: list[str]) -> list[dict]:
    seeds = []
    for src in sources:
        for line in (ROOT / src / "train.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            seeds.append({"seed_id": r["id"], "source": f"{src}/train.jsonl", "policy": r["policy"],
                          "sheets": r["sheets"], "program": r["program"], "trap": r.get("trap", "none"),
                          "domain": r.get("domain", "")})
    return seeds


def numbers_needed(program: str) -> set[str]:
    """Numbers the English must state: per-run caps and money amounts (trigger times are checked separately)."""
    return set(re.findall(r"up to (\d+)", program)) | set(re.findall(r"\$(\d+)(?:\.00)?\b", program))


def missing_times(program: str, text: str) -> list[str]:
    """Each trigger time must appear as 24-hour ("18:00") or 12-hour ("6pm", "6:30 am") time, or noon/midnight."""
    low, miss = text.lower(), []
    for hh, mm in re.findall(r"at (\d{2}):(\d{2})", program):
        h = int(hh)
        h12 = h % 12 or 12
        meridiem = r"(?:am|a\.m\.)" if h < 12 else r"(?:pm|p\.m\.)"
        minute = rf":{mm}" if mm != "00" else rf"(?::{mm})?"
        word = {12: "noon", 0: "midnight"}.get(h, "~")
        ok = (re.search(rf"\b{hh}:{mm}\b", low) or re.search(rf"\b{h12}{minute}\s*{meridiem}", low)
              or (mm == "00" and word in low))
        if not ok:
            miss.append(f"{hh}:{mm}")
    return miss


def prompt_for(seed: dict) -> list[dict]:
    hint = TRAP_HINTS.get(seed["trap"], "")
    return [
        {"role": "system", "content": "You write short requests from small-business owners to an assistant. Plain English, first person, no code."},
        {"role": "user", "content": (
            "Here is an automation that a business owner wants. Write the request the owner would send, as a short "
            "note in their own words. State every condition, time, limit, and who gets each message, but do not "
            "mention code, column names in backticks, or the word 'program'. " + hint + "\n\n"
            f"Sheets:\n{seed['sheets']}\n\nPolicy:\n{seed['policy']}\n\nAutomation:\n{seed['program']}\n\n"
            "Write only the owner's request.")},
    ]


def grams(text: str) -> set[str]:
    t = re.sub(r"\s+", " ", text.lower())
    return {t[i:i + 5] for i in range(max(len(t) - 4, 1))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--load-4bit", action="store_true", help="needs bitsandbytes (QLoRA-style loading for a 7B model)")
    ap.add_argument("--sources", nargs="+", default=["data/synthetic", "data/synthetic_traps", "data/synthetic_v3"])
    ap.add_argument("--per-program", type=int, default=3)
    ap.add_argument("--generation-timeout", type=float, default=180)
    ap.add_argument("--limit-programs", type=int, default=0, help="first N programs only (smoke test)")
    ap.add_argument("--temperature", type=float, default=0.9)
    ap.add_argument("--max-new-tokens", type=int, default=220)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="data/synthetic_v4")
    args = ap.parse_args()
    if args.per_program < 1 or args.limit_programs < 0 or args.max_new_tokens < 1 or args.generation_timeout <= 0:
        ap.error("counts and timeout must be positive (limit-programs may be zero)")

    from stages.gpu import gpu_job
    with gpu_job():
        run(args)


def run(args):
    use_repo_hf_cache()
    out = ROOT / args.out
    log = get_logger(out / "log.txt")
    lic = check_license(args.model, log)
    rev = model_revision(args.model)

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from data.gen.patterns import Sample
    from data.generate import verify
    from data.generate_traps import OverlapChecker
    from eval.bench import load_tasks

    seeds = load_seeds(args.sources)
    if args.limit_programs:
        seeds = seeds[: args.limit_programs]
    eval_sops = [t.sop for d in ("eval/benchmark", "eval/heldout", "eval/heldout2", "eval/heldout3") for t in load_tasks(ROOT / d)]
    overlap = OverlapChecker(eval_sops)
    config = {**vars(args), "revision": rev, "prompt_version": PROMPT_VERSION}
    config["seeds_sha256"] = hashlib.sha256(json.dumps(seeds, sort_keys=True).encode()).hexdigest()
    config_path = out / "run_config.json"
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError("Resume settings changed; choose a new output directory")
    write_json(config_path, config)
    ck = JsonlCheckpoint(out / "records.jsonl")
    log.info("%d seed programs x %d wordings; %d records already done", len(seeds), args.per_program, len(ck.done))

    tok = AutoTokenizer.from_pretrained(args.model, **model_load_kwargs(args.model))
    kw = {"device_map": "cuda"}
    if args.load_4bit:
        from transformers import BitsAndBytesConfig
        kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                       bnb_4bit_compute_dtype=torch.bfloat16)
    else:
        kw["dtype"] = torch.bfloat16
    model = AutoModelForCausalLM.from_pretrained(args.model, **model_load_kwargs(args.model), **kw)
    model.eval()
    started = time.time()
    for n, seed in enumerate(seeds):
        bad = verify(Sample("seed", seed["domain"], "", seed["policy"], seed["program"]))
        kept_grams: list[set[str]] = [grams(r["sop"]) for r in ck.records if r.get("seed_id") == seed["seed_id"] and r["accepted"]]
        for k in range(args.per_program):
            key = f"{seed['seed_id']}#{k}"
            if key in ck.done:
                continue
            rec = {"key": key, "seed_id": seed["seed_id"], "trap": seed["trap"], "policy": seed["policy"],
                   "sheets": seed["sheets"], "program": seed["program"], "accepted": False}
            text = ""
            if not bad:
                prompt = tok.apply_chat_template(prompt_for(seed), tokenize=False, add_generation_prompt=True)
                g = int(hashlib.sha256(f"{args.seed}:{key}".encode()).hexdigest()[:8], 16)
                torch.manual_seed(g)
                enc = tok([prompt], return_tensors="pt").to("cuda")
                with torch.inference_mode():
                    gen = model.generate(**enc, do_sample=True, temperature=args.temperature, top_p=0.95,
                                         max_time=args.generation_timeout,
                                         max_new_tokens=args.max_new_tokens, pad_token_id=tok.eos_token_id)
                text = tok.decode(gen[0, enc["input_ids"].shape[1]:], skip_special_tokens=True).strip().strip('"')
            words = len(text.split())
            missing = [x for x in numbers_needed(seed["program"]) if not re.search(rf"\b{x}\b", text)]
            missing += missing_times(seed["program"], text) if text else []
            j, s, sh = overlap.check(text, text) if text else (0, 0, 0)
            g5 = grams(text)
            near_dup = any(len(g5 & o) / max(len(g5 | o), 1) > 0.8 for o in kept_grams)
            reason = ("program: " + bad if bad else "code in text" if CODE.search(text) else
                      "length" if not 12 <= words <= 140 else f"missing numbers {missing}" if missing else
                      "near-duplicate" if near_dup else "overlaps an evaluation set" if (j >= 0.35 or s >= 0.75 or sh > 0)
                      else "")
            rec.update({"sop": text, "accepted": not reason, "reject_reason": reason,
                        "provenance": {"source": "local open-weight model", "model": args.model, "revision": rev,
                                       "license": lic, "prompt_version": PROMPT_VERSION, "seed_program": seed["source"],
                                       "temperature": args.temperature, "top_p": 0.95, "gen_seed": args.seed,
                                       "hosted_ai_text": False}})
            ck.add(rec)
            log.info("wording %s: %s", key, reason or "accepted")
            if not reason:
                kept_grams.append(g5)
        if (n + 1) % 25 == 0:
            acc = sum(r["accepted"] for r in ck.records)
            log.info("%d/%d programs, %d records, %d accepted, %.0f s", n + 1, len(seeds), len(ck.records), acc, time.time() - started)
    ck.close()

    kept = [r for r in ck.records if r["accepted"]]
    rows = {"train": [], "valid": []}
    for r in kept:  # split by seed program, so all wordings of one program land in the same split
        split = "valid" if int(hashlib.sha256(r["seed_id"].encode()).hexdigest(), 16) % 100 < 8 else "train"
        rows[split].append({"id": r["key"], "sop": r["sop"], "policy": r["policy"], "sheets": r["sheets"],
                            "program": r["program"], "trap": r["trap"], "provenance": r["provenance"]})
    for split, rs in rows.items():
        with (out / f"{split}.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for r in rs:
                f.write(json.dumps(r) + "\n")
    reasons: dict[str, int] = {}
    for r in ck.records:
        if not r["accepted"]:
            key = r["reject_reason"].split(" [")[0].split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1
    summary = {"stage": 3, "finished": True, "model": args.model, "revision": rev, "license": lic,
               "seed_programs": len(seeds), "records": len(ck.records), "accepted": len(kept),
               "train": len(rows["train"]), "valid": len(rows["valid"]), "rejected_by_reason": reasons,
               "seconds": round(time.time() - started), "sources": args.sources, "hosted_ai_text_used": False}
    write_json(out / "summary.json", summary)
    log.info("done: %s", json.dumps(summary))


if __name__ == "__main__":
    main()
