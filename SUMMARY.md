# Aether unattended session 2: 2026-10-26 evening to 2026-10-28

**Outcome: the data is cleaner and almost three times bigger, and the new 7B adapter was trained and tested on the dev split. It still does not beat v0.2:** 32 of 110 correct against v0.2's 34 (not a significant difference). So it is **not** worth spending the one-time held-out v3 run on. Nothing here is reviewed, and nothing says the model is safe: the only claim is what the checker verifies.

## Final dev table (110 benchmark tasks, dev split only)
Source: `eval/results/dev-report-q7b-v2-2026-10-27.json`.

| Run | Correct /110 | Non-trap /80 | Trap /30 | Parses | McNemar p vs v0.2 | Reused a training `about` line | Read a forbidden column |
|---|---|---|---|---|---|---|---|
| v0.2 (the released model) | 34 | 31 | 3 | 78% | - | 6 | 3 |
| Last attempt (v1, epoch 2) | 30 | 26 | 4 | 98% | 0.60 | 32 | 21 |
| New, epoch 1 | 32 | 28 | 4 | 97% | 0.86 | 28 | 22 |
| New, epoch 2 | 32 | 28 | 4 | 98% | 0.85 | 26 | 25 |

In plain words: the new model writes code that parses almost every time, and it got 2 more tasks right than the last attempt. But it still gets 2 fewer right than v0.2, and the gap is small enough to be chance. It still copies the first line of training programs about a quarter of the time (v0.2: 6 times), and it reads columns the policy forbids more often than before. The checker blocked every program that broke a rule, and no accepted program caused a monitor problem.

## What was done
1. **Mislabelled trap rows removed.** The tightened trap-ask filter was already the acceptance filter in the code; the old data had been built before it. A script (`stages/apply_trap_filter.py`) removed exactly the 28 flagged rows and kept their full records and provenance in `data/synthetic_v4/removed_rows.jsonl`. A test checks the real data.
2. **Review sample for you:** `docs/review/wordings-sample-2026-10-27.md`, 30 wordings picked by a fixed random seed (not by hand), with their program ids.
3. **More data.** The local Qwen2.5-7B model wrote wordings for **1,519 programs** (was 515), with traps at 27% of programs, like the benchmark: **2,401 train + 199 valid** wordings (was 898 + 67). On the new part, 55% of attempts were accepted, and none was a near-copy of the generator's English (highest similarity 0.225; limit 0.6).
4. **Training** with the same recipe as last time (only the data changed): 2 epochs, 302 steps. Validation loss 0.00919, then 0.00814.
5. **Dev evaluation** of both epochs against v0.2 (table above).

## Problems found and fixed
- **Validation stalled for 30+ minutes** at the end of epoch 1 (GPU memory full, Windows spilled to system RAM). Validation now uses the same answer-only loss as training: same number (unit-tested), about 2 minutes. Training resumed from the step-150 checkpoint.
- Stage 3 can now be extended (more programs, a set trap share) without changing anything that shapes a wording.
- Tests: 329 pass. No guard (GPU lock, licence, frozen hashes) was weakened.

## Needs you
1. Read the 30 sample wordings.
2. Decide the next experiment (suggestions in `HANDOFF.md`: train shorter, and look into why the model reads forbidden columns, before adding still more data).
3. Stage 5 still needs owner-reviewed `models.lock.json` entries for the older 1.5B and 0.5B base models.

The GPU is idle. Left alone: `pyproject.toml`, `uv.lock`, `data/synthetic_v4_smoke/`. Stage 5 was not run, held-out sets were not touched, and `stages/stage5_conditions.json` was not edited. Nothing was pushed, uploaded, installed, bought or signed in to.
