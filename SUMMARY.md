# Aether unattended session: 2026-10-26 (08:45 to 16:00)

**Outcome: stages 3 and 4 ran to completion, but the new model did not beat v0.2 on the dev split. Stage 5 (held-out v3) was not run.** Nothing here is reviewed, and nothing says the model is safe: the only claim is what the checker verified.

## What happened
- **Snapshots fixed.** Both Qwen 7B snapshots were completed from huggingface.co (no token), and offline preflight passed. Load probes: 5.69 GB peak GPU memory each (4-bit, inference).
- **Stage 3 data** (`data/synthetic_v4`): local Qwen2.5-7B-Instruct wrote 1,545 wordings over 515 seed programs. 965 were accepted (62.5%), giving 898 train and 67 valid rows (725 plain, 173 trap). The quality gate that replaces your review passed on the smoke run, the first 200 attempts, and the full run (`eval/results/stage3-quality-gate-*.json`).
- **Stage 4** (`outputs/qlora-7b-v1`, Qwen2.5-Coder-7B-Instruct QLoRA): 2 epochs, 114 steps, 76 minutes, no crash. Valid loss 0.0219 then 0.0173.
- **Dev comparison** (110 benchmark tasks, `safe_and_correct`): v0.2 34, new epoch 1 26, new epoch 2 **30** (27.3%). Paired McNemar vs v0.2: p = 0.23 and p = 0.60, so no significant difference, and the point estimate favours v0.2. The new adapter parses far more often (98% vs 78%) but gets effects wrong, and reads disallowed columns 15 times (v0.2: once). The checker blocked every rule-breaking program, and accepted programs had 0 monitor problems. A dev-only follow-up suggests why: the new adapter reuses a training program's `about` line in 31 of 110 outputs (v0.2: 6 of 110), so it partly recalls the 515 seed programs instead of following the request. That is a correlation, not a tested cause.
- **Candidate** (`outputs/qlora-7b-v1/epoch2`, chosen on dev over epoch 1) is written into `stages/stage5_conditions.json` and committed. Stage 5 was not run, and held-out v3 was not evaluated or opened.

## Problems I found and fixed (all logged with reasons in `HANDOFF.md`)
1. **Stage 3 seed order:** `--limit-programs 1000` would have used only plain programs (no traps, no v3). Added opt-in `--shuffle-seed`.
2. **Stage 3 prompt and filters:** `unsupported-post` had no hint. Wordings with invented numbers were being accepted. Added a hint and two stricter checks (invented numbers, missing trap ask). A `$0.00` threshold no longer demands the literal "0".
3. **Stage 4 slowdown:** step 2 of the first smoke took 707 s (GPU memory full, Windows spilled to system RAM). The loss now runs the output head on answer tokens only. It is the same loss: unit-tested, and the real step-1 loss matches to 5 decimals. Steps now take ~37 s.
4. **A CUDA "unknown error" crashed stage 3 once** at 10:34. I resumed it with the same command and lost no records.
Tests: 319 pass. No guard (GPU lock, licence, frozen hashes) was weakened.

## Needs you
1. Decide whether to spend the one-time held-out v3 run on this candidate. Dev suggests a null or negative result.
2. Read about 30 of the new wordings (`data/synthetic_v4/train.jsonl`, field `sop`). The automatic gate is shallow: in my hand check, 3 of 15 trap wordings did not clearly contain the unsafe ask.
3. Stage 5 also needs owner-reviewed `models.lock.json` entries for the older 1.5B and 0.5B base models.

The GPU is idle. Left alone: `pyproject.toml`, `uv.lock`, the old `data/synthetic_v4_smoke/`. Nothing was pushed, uploaded, installed, bought or signed in to. Evidence and exact commands: `HANDOFF.md` (top section) and `eval/results/` (files dated 2026-10-26, plus `eval/results/ft/qlora-7b-v1-*`).
