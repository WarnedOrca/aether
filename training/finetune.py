"""LoRA fine-tuning of a small open model on the verified synthetic dataset.

Runs on one consumer GPU (tested target: RTX 4070, 12 GB) or a free Kaggle/Colab GPU.
Only the assistant's program tokens are trained on (the prompt is masked out).

Usage:
  uv run --group ml python -m training.finetune --model Qwen/Qwen2.5-Coder-1.5B-Instruct --out outputs/ft-coder1.5b
Writes (in --out): adapter weights per epoch, train_log.jsonl (loss per step), run.json (config, eval loss).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def set_seed(seed: int) -> None:
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def load_split(name: str, with_traps: bool = False) -> list[dict]:
    rows = [json.loads(line) for line in (ROOT / "data/synthetic" / f"{name}.jsonl").open(encoding="utf-8")]
    if with_traps:  # v0.2: add trap-style samples (data/generate_traps.py)
        rows += [json.loads(line) for line in (ROOT / "data/synthetic_traps" / f"{name}.jsonl").open(encoding="utf-8")]
    return rows


def encode(tok, row: dict, max_len: int) -> dict | None:
    """Tokenize prompt + answer; labels are -100 on the prompt so only the program is learned."""
    from eval.prompt import chat_messages

    msgs = chat_messages(row["policy"], row["sheets"], row["sop"], fewshot=False)
    kwargs = {"tokenize": False}
    try:
        prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False, **kwargs)
    except TypeError:
        prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, **kwargs)
    answer = f"```aether\n{row['program']}\n```" + (tok.eos_token or "")
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    a_ids = tok(answer, add_special_tokens=False)["input_ids"]
    ids = p_ids + a_ids
    if len(ids) > max_len:
        return None
    return {"input_ids": ids, "labels": [-100] * len(p_ids) + a_ids}


def batches(items: list[dict], size: int, pad_id: int, shuffle: bool, rng: random.Random):
    import torch

    order = list(range(len(items)))
    if shuffle:
        rng.shuffle(order)
    for i in range(0, len(order), size):
        chunk = [items[j] for j in order[i:i + size]]
        n = max(len(x["input_ids"]) for x in chunk)
        ids = torch.full((len(chunk), n), pad_id)
        labels = torch.full((len(chunk), n), -100)
        mask = torch.zeros((len(chunk), n), dtype=torch.long)
        for k, x in enumerate(chunk):
            L = len(x["input_ids"])
            ids[k, :L] = torch.tensor(x["input_ids"])
            labels[k, :L] = torch.tensor(x["labels"])
            mask[k, :L] = 1
        yield ids, labels, mask


def evaluate(model, items, bs, pad_id, torch) -> float:
    model.eval()
    total, count = 0.0, 0
    with torch.no_grad():
        for ids, labels, mask in batches(items, bs, pad_id, False, random.Random(0)):
            out = model(input_ids=ids.cuda(), attention_mask=mask.cuda(), labels=labels.cuda())
            tokens = int((labels != -100).sum())
            total += float(out.loss) * tokens
            count += tokens
    model.train()
    return total / max(count, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    ap.add_argument("--out", default="outputs/ft-coder1.5b")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--micro", type=int, default=2)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=3072)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="train on N samples only (smoke test)")
    ap.add_argument("--with-traps", action="store_true", help="also train on data/synthetic_traps (v0.2)")
    args = ap.parse_args()

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup

    set_seed(args.seed)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    train_rows, valid_rows = load_split("train", args.with_traps), load_split("valid", args.with_traps)
    if args.limit:
        train_rows, valid_rows = train_rows[: args.limit], valid_rows[: max(8, args.limit // 10)]
    train = [x for x in (encode(tok, r, args.max_len) for r in train_rows) if x]
    valid = [x for x in (encode(tok, r, args.max_len) for r in valid_rows) if x]
    dropped = len(train_rows) - len(train)

    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16, device_map="cuda")
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    lora = LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05, task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lora)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.0)
    steps_per_epoch = math.ceil(len(train) / (args.micro * args.accum))
    sched = get_cosine_schedule_with_warmup(opt, int(0.05 * steps_per_epoch * args.epochs), steps_per_epoch * args.epochs)

    config = {**vars(args), "trainable_params": trainable, "train_examples": len(train), "valid_examples": len(valid),
              "dropped_too_long": dropped, "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0)}
    log = open(out / "train_log.jsonl", "w", encoding="utf-8")
    rng = random.Random(args.seed)
    step, started = 0, time.time()
    history = []
    model.train()
    for epoch in range(1, args.epochs + 1):
        for k, (ids, labels, mask) in enumerate(batches(train, args.micro, pad_id, True, rng)):
            loss = model(input_ids=ids.cuda(), attention_mask=mask.cuda(), labels=labels.cuda()).loss / args.accum
            loss.backward()
            if (k + 1) % args.accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                sched.step()
                opt.zero_grad()
                step += 1
                rec = {"step": step, "epoch": epoch, "loss": round(float(loss) * args.accum, 5),
                       "lr": sched.get_last_lr()[0], "elapsed_s": round(time.time() - started)}
                log.write(json.dumps(rec) + "\n")
                log.flush()
                if step % 10 == 0:
                    print(rec, flush=True)
        val = evaluate(model, valid, args.micro, pad_id, torch)
        history.append({"epoch": epoch, "valid_loss": round(val, 5), "elapsed_s": round(time.time() - started)})
        print(history[-1], flush=True)
        model.save_pretrained(out / f"epoch{epoch}")
    log.close()
    config["history"] = history
    config["seconds"] = round(time.time() - started)
    (out / "run.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
