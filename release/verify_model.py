"""Clean download-and-run test of the published LoRA adapter.

Downloads the adapter into a fresh temporary folder (no shared cache), checks the
weights file matches the local release build byte for byte, loads it on the base
model, generates programs for a few benchmark tasks, and scores them.

Usage:
  uv run --group ml python -m release.verify_model                       # from Hugging Face
  uv run --group ml python -m release.verify_model --source dist/model   # dry run on the local build
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_ID = "sidchalamala/aether-coder-1.5b-lora"
BASE = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
TASKS = ["physio-01", "coffee-01", "hw-04"]  # one reminder, one reorder, one trap (development set)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=REPO_ID, help="HF repo id, or a local folder for a dry run")
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="aether-verify-"))
    try:
        if Path(args.source).exists():
            adapter = tmp / "adapter"
            shutil.copytree(args.source, adapter)
            origin = f"local folder {args.source}"
        else:
            from huggingface_hub import snapshot_download
            adapter = Path(snapshot_download(args.source, cache_dir=str(tmp / "cache"),
                                             allow_patterns=["adapter_config.json", "adapter_model.safetensors"]))
            origin = f"Hugging Face {args.source}"
        weights = adapter / "adapter_model.safetensors"
        if not weights.exists():
            raise SystemExit(f"FAIL: adapter_model.safetensors not found in {origin}")
        local = ROOT / "dist/model/adapter_model.safetensors"
        same = local.exists() and sha256(weights) == sha256(local)
        print(f"source: {origin}\nsha256 matches local release build: {same}")

        from eval.baseline import Generator
        from eval.bench import load_tasks, score
        from eval.prompt import chat_messages, extract_program

        gen = Generator(BASE, str(adapter))
        tasks = {t.id: t for t in load_tasks()}
        picked = [tasks[i] for i in TASKS]
        outs = gen.generate([gen.prompt_text(chat_messages(t.policy, t.sheets, t.sop, fewshot=False)) for t in picked])
        for t, raw in zip(picked, outs):
            s = score(t, extract_program(raw))
            print(f"{t.id}: parse={s.parse} check={s.check} correct={s.safe_and_correct}")
        print("RESULT: adapter downloads, loads, and generates programs" + ("" if same else " (WARNING: weights differ)"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
