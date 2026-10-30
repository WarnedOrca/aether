# Aether session 5: 2026-10-29, the one-time held-out v3 run of v0.2

**Outcome: the released model v0.2 solves 18 of 72 brand-new tasks (95% CI 0.16-0.36) by itself, and 22 of 72 with checker feedback. The base model solves 2.** This is a modest result, in line with the earlier held-out sets. No statistical test was run, because the test declared in advance needed a 7B model and none was included (none beat v0.2 on dev). Nothing says the model is safe. The only claim is about the checker: the programs it accepted caused 0 monitor problems.

## Final held-out v3 table (72 tasks: 36 ordinary, 36 traps; 18 new business types)
Sources: `eval/results/stage5/summary.json`, `eval/results/stage5/report.json`.

| System | Correct /72 (95% CI) | Ordinary /36 (95% CI) | Traps /36 (95% CI) | Parses | Rejected by checker | Unsafe programs reaching execution |
|---|---|---|---|---|---|---|
| Base 1.5B + 3 examples | 2 (0.01-0.10) | 2 (0.02-0.18) | 0 (0.00-0.10) | 32% | 18 | 0 |
| **v0.2 plain (released)** | **18 (0.16-0.36)** | **13 (0.23-0.52)** | **5 (0.06-0.29)** | 81% | 25 | **0** |
| v0.2 with checker feedback | 22 (0.21-0.42) | 14 (0.25-0.55) | 8 (0.12-0.38) | 79% | 20 | 0 |

- **Statistical tests: none.** The only test declared before any v3 run was "the 7B model chosen on dev vs v0.2 plain". You excluded every 7B adapter, and you said not to add new comparisons, so there is no McNemar test and no adjusted p-value. All rows are descriptive and exploratory. Overlapping intervals mean the table does not show that feedback beats plain.
- **What the checker did:** it rejected 18, 25 and 20 programs, and every program it accepted ran with 0 monitor problems.

## What was done
1. **Pre-flight:** 336 tests passed and held-out v3 validated (72 tasks, 0 problems, frozen hashes unchanged). The 1.5B base model has a reviewed Apache-2.0 lock entry. The v0.2 adapter is byte-identical to the released one. Offline loading was checked on 2 development tasks.
2. **Last changes, no model change:** the README, `docs/RESULTS.md` and the model card template now include the three negative 7B experiments (dev only), each number tied to its result file. Inference settings were not changed: on dev, extra feedback rounds fixed nothing beyond the first.
3. **Freeze:** the conditions file (base, v0.2 plain, v0.2 with feedback; no 7B) was committed before the run, and its hash, the adapter's and the held-out files' are recorded in `HANDOFF.md`. Stage 5 can now resume after a crash without generating any task twice (tested). It was not needed: the run finished in 27 minutes without a crash.
4. **Run:** each condition was run once, and nothing was changed after seeing results.

**Held-out v3 is now used.** Any later model change needs a new frozen held-out set first.

## Needs you
1. Review the wording in the README and `docs/RESULTS.md` (the new 7B and held-out v3 sections) before anything is published. Nothing was pushed or uploaded, and the Hugging Face model card was not changed.
2. A new held-out set is needed before any further model work.

The GPU is idle. Left alone: `pyproject.toml`, `uv.lock`, `data/synthetic_v4_smoke/`. Nothing was pushed, uploaded, installed, bought or signed in to.
