# Aether session 4: 2026-10-28 to 2026-10-29 (dev split only)

**Question:** do the forbidden-column errors (E401) happen because, in the training data, the obvious column (usually `status`) is always allowed?

**Answer, in short: partly yes, but fixing it did not make the model better overall.** After adding training programs where the obvious column is NOT allowed, forbidden-column errors on the 110 dev tasks fell from 25 to 13, and forbidden `status` reads fell from 8 to 2. But the new model (q7b-v3 epoch 2) still solves 33 of 110 against v0.2's 34 (no real difference, p = 1.0), because it now gets more programs past the checker that do the wrong thing. Not worth the one-time held-out v3 run. Nothing says the model is safe: the only claim is what the checker verifies.

## Final dev table (110 tasks; source: `eval/results/session4-findings.json`)

| Model | Correct /110 | Non-trap /80 | Trap /30 | Forbidden column (E401) | Passes checker, wrong effects | McNemar p vs v0.2 |
|---|---|---|---|---|---|---|
| v0.2 (released) | 34 | 31 | 3 | 3 | 26 | - |
| Last model (q7b-v2 epoch 2) | 32 | 28 | 4 | 25 | 36 | 0.85 |
| New, epoch 1 | 29 | 24 | 5 | 13 | 51 | 0.51 |
| **New, epoch 2** | **33** | 24 | 9 | **13** | 50 | **1.0** |

With checker feedback (exploratory): new epoch 2 gets 36, v0.2 gets 36 (p = 1.0). Every run had 0 monitor problems; the checker blocked every program that broke a rule.

## What was done
1. **New training programs, made by a script** (`data/generate_counterfactual.py`): 534 programs taken from existing ones. In each, one filter condition is removed, and that column is taken off the policy's list of allowed columns but left in the sheet as a temptation. 20 different columns, `status` in 300 of them. Every program was checked by the parser, the checker and three monitored runs, and a test proves that putting the removed condition back makes the checker reject it. None matches a dev or held-out task. No new English was written: the local Qwen2.5-7B model wrote the owner requests, with the strict trap filter.
2. **Data:** 1,028 of 1,602 new wordings accepted (64%). They were added to the old data unchanged and make up 28% of it (target 25-30%).
3. **Training**, same recipe as before, on 3,351 rows. The computer shut down once mid-training; it resumed from a saved checkpoint and lost 21 steps.
4. **Dev evaluation** without and with checker feedback (table above).
5. **Model licences:** Qwen2.5-Coder-1.5B and 0.5B are both Apache-2.0 on Hugging Face (`eval/results/licence-check-older-bases-2026-10-28.json`) and are now in `models.lock.json` with their exact revisions.

## What we know vs what is only a guess
- **Known:** the new data changed the behaviour it targeted (E401 halved; `status` almost gone), but the overall score did not move. Trap tasks went up (4 to 9) and non-trap tasks went down (28 to 24).
- **Guess:** the new programs teach "drop the condition on the forbidden column", while the dev tasks still need that condition written with a different, allowed column. So the model may now leave conditions out, which would explain the extra wrong-effect programs. The trap gain may come from the extra trap wordings rather than from this change. One training run cannot tell these apart.

## Needs you
1. Truly new column names would have to be invented, which would be hosted-AI text in training data, so I did not. You could write a list yourself, or accept the 20 existing columns.
2. Decide the next experiment. One idea: counterfactuals that keep the condition but on a different allowed column, so the model learns "use the allowed column" instead of "drop the condition". This needs a rule for which columns mean the same thing, which is a data decision.
3. The two older base models are in the default Hugging Face cache, not the repo cache (offline runs need `HF_HOME` set to it).

The GPU is idle. Stage 5 was not run, held-out sets were not touched, and `stages/stage5_conditions.json` was not edited. Left alone: `pyproject.toml`, `uv.lock`, `data/synthetic_v4_smoke/`. Nothing was pushed, uploaded, installed, bought or signed in to.
