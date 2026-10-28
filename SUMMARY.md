# Aether unattended session 2: 2026-10-26 evening to 2026-10-27 22:55

**Outcome: the data is cleaner and almost three times bigger, and a new 7B adapter is trained. Its dev evaluation has NOT been run yet** (you needed to shut the computer down just as it started). So there is no new dev table, and nothing yet says whether the new adapter beats v0.2. Nothing here is reviewed, and nothing says the model is safe: the only claim is what the checker verifies.

## What was done
1. **Mislabelled trap rows removed.** The tightened trap-ask filter was already the acceptance filter in the code; the old data had been built before it. A script (`stages/apply_trap_filter.py`) removed exactly the 28 flagged rows (27 train, 1 valid) and kept their full records and provenance in `data/synthetic_v4/removed_rows.jsonl`. A test checks the real data.
2. **Review sample for you:** `docs/review/wordings-sample-2026-10-27.md`, 30 wordings picked by a fixed random seed (not by hand), with their program ids. Please read them: the automatic checks only look at structure, not meaning.
3. **More data.** The local Qwen2.5-7B model wrote wordings for more seed programs: **1,519 programs** now (was 515), with traps at 27% of programs, like the benchmark. Accepted wordings: **2,401 train + 199 valid** (was 898 + 67). On the new part, 55% of attempts were accepted, and no wording was a near-copy of the generator's English (highest similarity 0.225; the limit is 0.6). Result file: `eval/results/stage3-quality-gate-new-part-2026-10-27.json`.
4. **Training** with the same recipe as last time (only the data changed): 2 epochs, 302 steps, about 3.3 hours of training. Validation loss 0.00919 after epoch 1 and 0.00814 after epoch 2. Training loss again gets very small, so memorisation is still possible; only the dev run can tell.

## Problems found and fixed
- **Validation stalled for 30+ minutes** at the end of epoch 1 (GPU memory full, Windows spilled to system RAM: the same problem as the earlier 707 s training step). Validation still used the old full-vocabulary loss. It now uses the same answer-only loss as training: same number (unit-tested), about 2 minutes instead of a stall. Training resumed from the step-150 checkpoint.
- Stage 3 can now be extended (more programs, a set trap share) without changing anything that shapes a wording. The resume check still refuses changed model, prompt or sampling settings.
- Tests: 329 pass. No guard (GPU lock, licence, frozen hashes) was weakened.

## Next (about 30 minutes of GPU time)
Run `bash logs/run-chain2-2026-10-27.sh` from the repo, or the three commands at the top of `HANDOFF.md`. It evaluates both epochs on the 110 dev tasks and writes `eval/results/dev-report-q7b-v2-2026-10-27.json` with correct / non-trap / trap / parse rate / McNemar p vs v0.2 / reused training `about` lines / forbidden-column count. Stage 5 and held-out v3 stay untouched until you decide.

## Needs you
1. Read the 30 sample wordings.
2. Run the dev evaluation (above), or ask an agent to.
3. Stage 5 still needs owner-reviewed `models.lock.json` entries for the older 1.5B and 0.5B base models.

The GPU is idle. Left alone: `pyproject.toml`, `uv.lock`, `data/synthetic_v4_smoke/`. Nothing was pushed, uploaded, installed, bought or signed in to.
