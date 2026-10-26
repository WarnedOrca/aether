# AGENTS.md: instructions for Codex and other coding agents

You are working on **Aether**: a small language for checkable business procedures, a static checker, a sandboxed interpreter with an independent monitor, an AI-drafted benchmark, and small fine-tuned open models that turn plain-English procedures (SOPs) into Aether programs. The owner is a high school student. Explain every decision in plain language in `HANDOFF.md`.

Read first: this file, `HANDOFF.md` (current state and next steps), `README.md`, `docs/RESULTS.md`, `spec/SPEC.md` (sections 5 and 13).

## Rules that never change
1. **Budget is $0.** No paid APIs, GPUs, services, plans, or trials. No new accounts. Never enter or ask for payment details.
2. **Never invent numbers or citations.** Every reported number must come from a committed result file in `eval/results/`. If you did not run it, do not report it.
3. **Never call the model or the system "safe".** The only claim is what the checker verifies (core rules C1-C8 for Aether programs). Say "the checker blocked every program that broke a rule"; never "the model is safe".
4. **Held-out discipline.** `eval/heldout/`, `eval/heldout2/` and `eval/heldout3/` are frozen (SHA-256 in each `FROZEN.md`; `tests/test_heldout_frozen.py` fails if they change). Never edit them, train on them, tune on them, or use them to choose anything. Make all choices on the dev split (`eval/benchmark/`, and the used held-out v1/v2). Run each final condition on held-out v3 **once**. Before any further model change after that, a new held-out set must be frozen first.
5. **Training-data provenance.** No text written by Claude, ChatGPT, or any other hosted AI (Anthropic, OpenAI, etc.) may be used as training data. Allowed: human-written text, script-generated data, and text from open-weight models **run locally** (prefer Apache-2.0; check the licence on the model's Hugging Face page first and stop if it is not Apache-2.0 or MIT). Record provenance for every training example. The held-out and benchmark tasks were drafted by Claude: they are evaluation-only and must never become training data.
6. **No pushing or publishing without the owner's review.** Do not `git push`, upload to Hugging Face, post, or change published numbers. Commit locally only.
7. **Secrets.** Never ask for, read, print, or store passwords, tokens, API keys, or 2FA codes. If something needs a sign-in, stop and write it in `HANDOFF.md` under "Needs the owner".
8. Stop and write to `HANDOFF.md` (do not guess) if a step needs a purchase, a new account, a sign-in, a new dependency, or a decision about the language or the data.

## Environment rules for Codex on this Windows machine
- Use the project interpreter directly: `.venv\Scripts\python.exe`. **Never run `uv sync`, `uv run`, or `pip install`.** uv is not on Codex's PATH, and a sync could rebuild the environment in the middle of a run (that already crashed a training run once). If a package is missing, stop and write it under "Needs the owner".
- Set the Hugging Face cache inside the repo for every command that downloads models: `$env:HF_HOME = "$PWD\.hf-cache"` (the stage scripts also do this by default). `.hf-cache/`, model weights (`*.safetensors`, `*.bin`, `*.pt`), `outputs/`, checkpoints (`ckpt-*`), and `logs/` are gitignored; never commit them, never force-add them.
- Run long jobs **detached** with log files, then poll the logs; do not keep a terminal blocked for hours. Example (PowerShell):
  ```powershell
  New-Item -ItemType Directory -Force logs | Out-Null
  $env:HF_HOME = "$PWD\.hf-cache"
  Start-Process -FilePath .venv\Scripts\python.exe -ArgumentList '-u','-m','stages.stage3_paraphrase','--limit-programs','20','--out','data/synthetic_v4_smoke' -RedirectStandardOutput logs\stage3-smoke.out -RedirectStandardError logs\stage3-smoke.err -WindowStyle Hidden
  Get-Content logs\stage3-smoke.out -Tail 20     # poll every few minutes
  Get-Content data\synthetic_v4_smoke\log.txt -Tail 20
  ```
- Ignore the harmless git warning about `%USERPROFILE%\.config\git\ignore` (permission denied); it does not affect the repo.
- Only one GPU job at a time (one 12 GB GPU). Check with `nvidia-smi` before starting one.

## Current state (2026-10-25, end of day)
- Released model: **v0.2** (LoRA on Qwen2.5-Coder-1.5B-Instruct), on Hugging Face `sidchalamala/aether-coder-1.5b-lora`. v0.3 is an unreleased negative result.
- Held-out v2 (90 tasks): base 1/90, v0.2 plain 20/90, v0.3 plain 14/90; the pre-registered comparison (v0.3 with checker feedback vs v0.2 plain) was a null result (p = 0.33). In every evaluation the checker blocked every program that broke a rule, and accepted programs had 0 monitor violations.
- Stage 1 diagnosis (dev only): `eval/results/diagnosis-v0.2-dev-2026-10-25.json`. Stage 2: held-out v3 frozen (72 tasks, 36 traps) in commit `bae67f7`, with metrics declared before any run (see `HANDOFF.md`).
- Stages 3-5 are prepared as scripts in `stages/` but **not run**. Nothing has been generated or trained for them.

## Exact commands to resume
```powershell
cd <path to this repo>
git status
git log --oneline -5
.venv\Scripts\python.exe -m pytest -q                                   # all tests must pass
.venv\Scripts\python.exe -m eval.validate_tasks eval\heldout3           # expect 72 tasks, 0 problems
Get-Content HANDOFF.md
```
Then continue from "Next steps" in `HANDOFF.md`. Stage scripts (each resumes after a crash, logs to files, and writes `summary.json` when finished):
- Stage 3 data: `.venv\Scripts\python.exe -u -m stages.stage3_paraphrase --out data/synthetic_v4 --per-program 3 [--load-4bit] [--limit-programs N]`
- Stage 4 training: `.venv\Scripts\python.exe -u -m stages.stage4_qlora --model Qwen/Qwen2.5-Coder-7B-Instruct --data data/synthetic_v4 --out outputs/qlora-7b-v1 [--limit 64]`
- Stage 5 final eval (once): copy `stages/stage5_conditions.example.json` to `stages/stage5_conditions.json`, fill in the adapter chosen on the dev split, commit it, then `.venv\Scripts\python.exe -u -m stages.stage5_eval --conditions stages/stage5_conditions.json`
Rerunning any stage command after a crash continues where it stopped.

## At the end of every session
Update **`HANDOFF.md` in this repo** (not any other notes folder): what you did, the exact commands and their result files, what failed and why, current state, next steps, and "Needs the owner". Commit locally with a Conventional Commit message. Do not push.
