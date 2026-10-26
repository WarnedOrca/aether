"""Stage 4: QLoRA fine-tuning of a ~7B code model on a 12 GB GPU, with resumable checkpoints.

- Checks the model licence on its Hugging Face page first and stops unless it is Apache-2.0 or MIT.
- Loads the base model in 4-bit (bitsandbytes NF4), trains a LoRA adapter, same prompt and masking as training/finetune.py.
- Saves a resumable checkpoint (adapter + optimizer + scheduler + RNG + position) every --save-every optimizer steps,
  keeps the last 2, and resumes from the newest one after a crash. An adapter is also saved at the end of each epoch.
- Logs to <out>/log.txt and <out>/train_log.jsonl; writes <out>/summary.json when finished.
- Chooses nothing on held-out data: validation loss uses the training data's own valid split only.

Usage (detached):
  .venv\\Scripts\\python.exe -m stages.stage4_qlora --model Qwen/Qwen2.5-Coder-7B-Instruct --data data/synthetic_v4 --out outputs/qlora-7b-v1
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import time
from pathlib import Path

from stages.common import ROOT, model_load_kwargs, check_license, get_logger, model_revision, use_repo_hf_cache, write_json
from training.finetune import batches, encode, evaluate, set_seed


def load_rows(folders: list[str], split: str) -> list[dict]:
    rows = []
    for f in folders:
        rows += [json.loads(line) for line in (ROOT / f / f"{split}.jsonl").open(encoding="utf-8")]
    return rows


def latest_checkpoint(out: Path) -> Path | None:
    cks = sorted(out.glob("ckpt-*"), key=lambda p: int(p.name.split("-")[1]))
    return next((c for c in reversed(cks) if (c / "state.json").exists()), None)  # state.json is written last


def answer_only_loss(model, ids, labels, mask):
    """Same value as model(..., labels=labels).loss, but the output head only runs on the answer tokens.
    The prompt is ~1000 of ~1350 tokens and is masked, and full-vocabulary logits for it overflow a 12 GB GPU
    (Windows then spills to system memory and training slows ~17x)."""
    import torch

    n = ids.shape[1]
    first = int((labels != -100).any(dim=0).nonzero()[0])  # first position holding an answer token in any row
    keep = n - first + 1  # logits for positions first-1 .. n-1; the last one predicts nothing
    logits = model(input_ids=ids, attention_mask=mask, logits_to_keep=keep).logits[:, :-1].float()
    targets = labels[:, n - keep + 1:]
    return torch.nn.functional.cross_entropy(logits.reshape(-1, logits.shape[-1]), targets.reshape(-1), ignore_index=-100)


def accumulation_size(k: int, total_batches: int, accum: int) -> int:
    return min(accum, total_batches - (k // accum) * accum)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    ap.add_argument("--data", nargs="+", default=["data/synthetic_v4"], help="folders with train/valid.jsonl")
    ap.add_argument("--out", default="outputs/qlora-7b-v1")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--micro", type=int, default=1)
    ap.add_argument("--accum", type=int, default=16)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=2048)
    ap.add_argument("--save-every", type=int, default=25)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="train on N samples only (smoke test)")
    args = ap.parse_args()
    if args.data != ["data/synthetic_v4"]:
        ap.error("Owner decision: stage 4 trains only on data/synthetic_v4")
    if min(args.epochs, args.micro, args.accum, args.save_every, args.max_len, args.rank) < 1:
        ap.error("training counts must be positive")

    from stages.gpu import gpu_job
    with gpu_job():
        run(args)


def run(args):
    use_repo_hf_cache()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    log = get_logger(out / "log.txt")
    lic = check_license(args.model, log)
    rev = model_revision(args.model)
    config = {**vars(args), "revision": rev}
    config["data_sha256"] = {}
    import hashlib
    for split in ("train", "valid"):
        path = ROOT / args.data[0] / f"{split}.jsonl"
        config["data_sha256"][split] = hashlib.sha256(path.read_bytes()).hexdigest()
    config_path = out / "run_config.json"
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError("Resume data/settings changed; choose a new output directory")
    write_json(config_path, config)

    import torch
    from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, get_cosine_schedule_with_warmup

    set_seed(args.seed)
    tok = AutoTokenizer.from_pretrained(args.model, **model_load_kwargs(args.model))
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    train_rows, valid_rows = load_rows(args.data, "train"), load_rows(args.data, "valid")
    if args.limit:
        train_rows, valid_rows = train_rows[: args.limit], valid_rows[: max(8, args.limit // 10)]
    train = [x for x in (encode(tok, r, args.max_len) for r in train_rows) if x]
    valid = [x for x in (encode(tok, r, args.max_len) for r in valid_rows) if x]
    if not train or not valid:
        raise ValueError("No usable train or validation examples; stopping before model load")

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(args.model, **model_load_kwargs(args.model), quantization_config=bnb, device_map="cuda")
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    ck = latest_checkpoint(out)
    if ck:
        model = PeftModel.from_pretrained(model, ck / "adapter", is_trainable=True)
    else:
        lora = LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05, task_type="CAUSAL_LM",
                          target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
        model = get_peft_model(model, lora)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
    steps_per_epoch = math.ceil(len(train) / (args.micro * args.accum))
    total = steps_per_epoch * args.epochs
    sched = get_cosine_schedule_with_warmup(opt, int(0.05 * total), total)

    state = {"step": 0, "epoch": 1, "micro_in_epoch": 0, "history": [], "elapsed_s": 0}
    if ck:
        state = json.loads((ck / "state.json").read_text(encoding="utf-8"))
        opt.load_state_dict(torch.load(ck / "optimizer.pt", weights_only=False))
        sched.load_state_dict(torch.load(ck / "scheduler.pt", weights_only=False))
        torch.set_rng_state(torch.load(ck / "rng_cpu.pt", weights_only=False))
        torch.cuda.set_rng_state_all(torch.load(ck / "rng_cuda.pt", weights_only=False))
        log.info("resumed from %s at step %d (epoch %d)", ck.name, state["step"], state["epoch"])
    log.info("model %s (%s), %d train / %d valid examples, %d optimizer steps total", args.model, lic, len(train), len(valid), total)

    def save(tag: str) -> None:
        d = out / f"ckpt-{state['step']}"
        tmp = out / f".tmp-{tag}"
        shutil.rmtree(tmp, ignore_errors=True)
        model.save_pretrained(tmp / "adapter")
        torch.save(opt.state_dict(), tmp / "optimizer.pt")
        torch.save(sched.state_dict(), tmp / "scheduler.pt")
        torch.save(torch.get_rng_state(), tmp / "rng_cpu.pt")
        torch.save(torch.cuda.get_rng_state_all(), tmp / "rng_cuda.pt")
        write_json(tmp / "state.json", state)
        shutil.rmtree(d, ignore_errors=True)
        tmp.rename(d)
        for old in sorted(out.glob("ckpt-*"), key=lambda p: int(p.name.split("-")[1]))[:-2]:
            shutil.rmtree(old, ignore_errors=True)

    started = time.time() - state["elapsed_s"]
    tlog = (out / "train_log.jsonl").open("a", encoding="utf-8")
    model.train()
    total_batches = math.ceil(len(train) / args.micro)
    for epoch in range(state["epoch"], args.epochs + 1):
        rng = random.Random(args.seed * 1000 + epoch)  # same order for an epoch after a resume
        for k, (ids, labels, mask) in enumerate(batches(train, args.micro, pad_id, True, rng)):
            if k < state["micro_in_epoch"]:
                continue
            group_size = accumulation_size(k, total_batches, args.accum)
            loss = answer_only_loss(model, ids.cuda(), labels.cuda(), mask.cuda()) / group_size
            loss.backward()
            if (k + 1) % args.accum and k + 1 != total_batches:
                continue
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            torch.cuda.empty_cache()  # keep the allocator from growing into Windows shared memory
            state.update(step=state["step"] + 1, epoch=epoch, micro_in_epoch=k + 1, elapsed_s=round(time.time() - started))
            rec = {"step": state["step"], "epoch": epoch, "loss": round(float(loss) * group_size, 5),
                   "lr": sched.get_last_lr()[0], "elapsed_s": state["elapsed_s"]}
            tlog.write(json.dumps(rec) + "\n")
            tlog.flush()
            if state["step"] % 10 == 0:
                log.info("%s", rec)
            if state["step"] % args.save_every == 0:
                save("step")
        torch.cuda.empty_cache()
        val = evaluate(model, valid, args.micro, pad_id, torch)
        torch.cuda.empty_cache()
        state["history"].append({"epoch": epoch, "valid_loss": round(val, 5), "elapsed_s": round(time.time() - started)})
        log.info("epoch %d valid loss %.5f", epoch, val)
        model.save_pretrained(out / f"epoch{epoch}")
        state.update(epoch=epoch + 1, micro_in_epoch=0)
        save("epoch")
    tlog.close()
    summary = {"stage": 4, "finished": True, **{k: v for k, v in vars(args).items()}, "license": lic, "revision": rev,
               "train_examples": len(train), "valid_examples": len(valid), "steps": state["step"],
               "history": state["history"], "seconds": round(time.time() - started),
               "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0)}
    write_json(out / "summary.json", summary)
    log.info("done: %s", json.dumps(summary))


if __name__ == "__main__":
    main()
