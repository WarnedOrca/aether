# Aether session 3: 2026-10-28 (dev split only, no training)

**Outcome: we now know where the new 7B model fails, and checker feedback does not separate it from v0.2.** With checker feedback, the new model (q7b-v2 epoch 2) solves 35 of 110 dev tasks and v0.2 solves 36 (exploratory, p = 1.0). Nothing here changes the earlier decision: no candidate is worth the one-time held-out v3 run. Nothing says the model is safe: the only claim is what the checker verifies.

## 1. Why the new model fails (from saved outputs, no model run)
Source: `eval/results/dev-failure-diagnosis-2026-10-28.json`.
- The new model almost always writes code that parses (2 parse failures vs 24 for v0.2), but more of its code does the wrong thing (36 vs 26), and 25 of its programs use a column the policy forbids (v0.2: 3).
- **The forbidden-column problem is the model, not the tasks.** On the 25 tasks where the new model makes that error, v0.2 makes it only once. In all 25 cases the program names the right policy and then still uses a column the policy does not allow. So the model copies the policy line but does not follow it.
- **Why, partly a guess:** 8 of the 25 are the `status` column, which 2,254 of the 2,401 training programs filter on, so it is probably a trained habit. The other columns appear in no training program, so habit does not explain them. The model may pick the column that sounds right instead of the one it is allowed to use (not tested).
- Trap tasks: the new model's most common trap failure is this same error (12 of 30 trap tasks).

## 2. Memorisation (from saved outputs)
Source: `eval/results/dev-memorisation-2026-10-28.json`.
- The new model reuses a training program's first line (`about "..."`) in 26 of 110 outputs (v0.2: 6). But those outputs are **not** more often wrong: 10 of 26 correct, against 22 of 84 for the rest.
- I could not show that whole programs are copied: Aether programs all have a similar shape, so they look as much like the right answer as like the training program. The earlier "it recalls training programs" explanation is therefore weaker than it seemed.

## 3. Checker feedback (GPU, exploratory)
Sources: `eval/results/repair-q7b-v2-epoch2-dev-benchmark.json`, `eval/results/repair-v0.2-dev-rerun-benchmark.json`, `eval/results/dev-repair-compare-2026-10-28.json`.

| Model | Without feedback | With feedback | Non-trap /80 | Trap /30 |
|---|---|---|---|---|
| New 7B (q7b-v2 epoch 2) | 32 | 35 | 31 | 4 |
| v0.2 | 34 | 36 | 32 | 4 |

- Head to head with feedback: 16 tasks only the new model solves, 17 only v0.2; exact McNemar p = 1.0. Exploratory, not confirmatory.
- Feedback cuts the new model's forbidden-column errors from 25 to 16. But programs that pass the checker and still do the wrong thing rise from 36 to 49. The feedback gets programs past the checker without making them do what the owner asked.
- The checker blocked every program that broke a rule, and accepted programs caused 0 monitor problems.

## What changed in the code
- `eval/repair.py` now saves after every task and continues where it stopped (tested with a simulated crash). New CPU scripts: `eval/dev_failure_analysis.py`, `eval/dev_memorisation_check.py`, `eval/dev_repair_compare.py`. 330 tests pass.

## Needs you
1. Decide the next experiment. The evidence points at the policy allow-list being ignored, not at too little data. One idea (your data decision): training examples where the obvious column is not allowed.
2. v0.2 ran in normal (not offline) mode from the default Hugging Face cache, as on 2026-10-25, because its base model has no reviewed `models.lock.json` entry. Adding one is your call.
3. Still open from before: read the 30 sample wordings in `docs/review/wordings-sample-2026-10-27.md`.

The GPU is idle. Stage 5 was not run, held-out sets were not touched, and `stages/stage5_conditions.json` was not edited. Left alone: `pyproject.toml`, `uv.lock`, `data/synthetic_v4_smoke/`. Nothing was pushed, uploaded, installed, bought or signed in to.
