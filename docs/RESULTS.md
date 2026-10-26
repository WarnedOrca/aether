# Results (2026-10-25)

Published artifacts: model https://huggingface.co/sidchalamala/aether-coder-1.5b-lora, data https://huggingface.co/datasets/sidchalamala/aether-sop-programs, benchmark and held-out set https://huggingface.co/datasets/sidchalamala/aether-benchmark, code https://github.com/WarnedOrca/aether, browser demo (checker and interpreter only; model not hosted) https://warnedorca.github.io/aether/.

All numbers come from committed files in `eval/results/`. Each is a single run with greedy decoding on one local RTX 4070 GPU.

"Correct" (scorer field `safe_and_correct`) means: passes the checker AND has the same effects as the reference program. It is not a safety rating, and neither the model nor the system should be called "safe".

**Released model: v0.2.** v0.1 is documented for comparison. Model names: **v0.1** is a LoRA on 1,649 synthetic samples. **v0.2** is the same recipe plus 413 trap-style samples (`data/synthetic_traps/`). Both adapt Qwen2.5-Coder-1.5B-Instruct.

## 1. Final evaluation: frozen held-out trap set (clean)

30 trap tasks in 10 new business types (`eval/heldout/`, SHA-256 in `FROZEN.md`). The set was frozen before any trap training data existed and never used for any decision. Each model was evaluated on it exactly once. 4 tasks use novel trap types (delete-data, raise-limit) that are absent from all training data.

| System | correct | 95% CI | known types (26) | novel types (4) | parse | check |
|---|---|---|---|---|---|---|
| Base model, reference card + 3 examples | 0/30 | 0.00-0.11 | 0 | 0 | 8 | 0 |
| v0.1, reference card | 6/30 | 0.10-0.37 | 6 | 0 | 26 | 9 |
| v0.2 (+ trap data), reference card | 6/30 | 0.10-0.37 | 6 | 0 | 25 | 11 |

Paired exact McNemar tests (`eval/results/ft/heldout-*.json`):
- v0.2 vs v0.1: 1 task only v0.2 solved, 1 task only v0.1 solved, p = 1.0. **No measurable improvement from the trap data.**
- v0.1 vs base and v0.2 vs base: 6 vs 0, p = 0.031.

**v0.2 failure breakdown (24 tasks):**
- about 7 followed the unsafe or impossible instruction (a private field in a message, or messaging where the policy allows none)
- about 13 were general mistakes on unfamiliar businesses: 5 parse errors, plus type errors, reading columns the policy does not allow, and `skip` outside a loop
- about 4 did roughly what the reference does, but with a different number of owner notes

**The checker blocked every program that broke a rule, and programs it accepted had 0 monitor violations.**

## 1b. Held-out v2: 90 tasks (clean; plan pre-registered)

90 tasks (30 traps, 60 general) in 15 business types not used anywhere else (`eval/heldout2/`, SHA-256 in `FROZEN.md`), drafted by Claude and frozen before any v0.3 training, tuning, or repair/decoding experiments. Before the run, one primary comparison was pre-registered (vault decision log, 2026-10-25): **v0.3 with checker feedback vs v0.2 plain** on `safe_and_correct`, exact McNemar, alpha 0.05. Every condition was run exactly once, in one script (`eval/run_final_v2.sh`, log `eval/results/final-v2-log.txt`). Report: `eval/results/final-v2-report-2026-10-25.json`.

| System | correct (of 90) | 95% CI | traps (of 30) | status |
|---|---|---|---|---|
| Base model, reference card + 3 examples | 1 | 0.00-0.06 | 0 | exploratory |
| **v0.2 plain (released)** | **20** | 0.15-0.32 | 2 | primary comparator |
| v0.2 with checker feedback | 22 | 0.17-0.34 | 2 | exploratory |
| v0.2 grammar-constrained | 19 | 0.14-0.31 | 2 | exploratory |
| v0.3 plain (not released) | 14 | 0.10-0.24 | 3 | exploratory |
| v0.3 with checker feedback (not released) | 15 | 0.10-0.26 | 3 | primary |
| v0.3 grammar-constrained (not released) | 15 | 0.10-0.26 | 3 | exploratory |

- **Primary result: null.** v0.3 with checker feedback 15 vs v0.2 plain 20; 6 tasks only v0.3 solved, 11 only v0.2 solved; exact McNemar p = 0.33. The new data plus checker feedback did not improve on the released model.
- v0.2 plain vs base: 20 vs 1, p = 2.1e-5 (`eval/results/ft/heldout2-v0.2-vs-base.json`; not pre-registered).
- **Conditions.** *Plain*: one greedy answer. *With checker feedback* (`eval/repair.py`): if the program fails to parse or fails the checker, the model gets the error messages and tries again, up to 3 times; nothing else is shown to it. Plain and checker-feedback results are separate rows, never blended. *Grammar-constrained* (`eval/constrained.py`): at each step, only the top-8 tokens that keep the output a valid Aether prefix are allowed (fallback to the unconstrained token when none is: 497 of 15,184 steps for v0.2, 341 of 14,936 for v0.3).
- **v0.3** (`eval/results/ft/ft-coder1.5b-v0.3-run.json`): the v0.2 recipe plus 1,232 checker-verified samples from 30 new business types (`data/synthetic_v3/`), 3,294 training examples. Like v0.1 and v0.2, it scores 100/100 on its synthetic test split, but lower than v0.2 on held-out v2 and on the development benchmark (26/110 vs 34/110). Our reading (a hypothesis, not tested): the generated data teaches the generator's templates more than reading real SOPs. **v0.3 is not released.**
- Development-only results that came before the held-out run: checker feedback on the 110-task benchmark, v0.2 34 -> 36; grammar-constrained, 33 (parse rate 0.78 -> 0.88).

## 2. Development benchmark: 110 tasks, used during development

This benchmark was used to build and debug the scorer, the blank-cell rule, and the SOP wording, and to compare models during development. Treat it as a development set, not a clean test.

| System | Prompt | correct | parse | check | traps (n=30) | synthetic test (n=100) |
|---|---|---|---|---|---|---|
| Qwen2.5-Coder-0.5B-Instruct | card + 3 examples | 0.000 | 0.391 | 0.000 | 0 | 0.06 |
| Qwen2.5-Coder-1.5B-Instruct | card only | 0.000 | 0.000 | 0.000 | 0 | 0.00 |
| Qwen2.5-Coder-1.5B-Instruct | card + 3 examples | 0.027 | 0.282 | 0.036 | 0 | 0.03 |
| Qwen3-1.7B | card + 3 examples | 0.018 | 0.236 | 0.045 | 0 | 0.08 |
| SmolLM2-1.7B-Instruct | card + 3 examples | 0.009 | 0.336 | 0.018 | 0 | 0.07 |
| v0.1 | card only | 0.273 (30/110, 95% CI 0.198-0.363) | 0.827 | 0.536 | 2/30 | 1.00 |
| v0.2 | card only | 0.309 (34/110) | 0.782 | 0.545 | 3/30 | 1.00 |

v0.1 vs the base model with 3 examples: 30 vs 3, exact McNemar p = 1.4e-6. v0.2 vs v0.1: 34 vs 30, p = 0.48 (not significant).

## 3. Checker and interpreter

| Check | Result | Source |
|---|---|---|
| Test suite | all pass (`uv run pytest`) | `tests/` |
| Property tests P1-P9 | 25,000 generated cases, 0 violations | `eval/results/properties-2026-10-24.json` |
| Checker mutation testing | 88 rule-breaking mutants, 88 rejected with the expected error code | same file |
| Planted interpreter bugs | the independent monitor caught all 5 kinds | `tests/test_monitor_catches_bugs.py` |

These results support only this statement: the checker verifies core rules C1-C8 for programs in the Aether language, under the trust assumptions in `spec/SPEC.md` section 5.

## What this shows

- Fine-tuning on checker-verified synthetic data takes a 1.5B model from 0 to a useful level on hand-written tasks (development: 30/110 vs 3/110; held-out traps: 6/30 vs 0/30).
- **Adding trap-style synthetic data did not improve trap handling** (held-out: 6/30 for both v0.1 and v0.2). Most remaining failures are general robustness errors on new business types, not only trap-following. Fixing that probably needs more varied training language or a larger model, not more templated traps.
- **More varied generated data, checker feedback, and grammar-constrained decoding did not measurably help on held-out v2** (pre-registered null, p = 0.33). A model that is perfect on its own synthetic test can still be worse on new SOPs.
- **Blocking rule-breaking programs is the checker's job, not the model's.** In every evaluation, the checker blocked every program that broke a rule, and programs it accepted had 0 monitor violations. The model by itself solves 6/30 held-out traps.
## Limitations

- All benchmark and held-out tasks were drafted by Claude (an AI assistant), not taken from real businesses.
- The training English is templated (rule-based generator). Most held-out failures are general errors on unfamiliar businesses.
- Small evaluation sets with wide intervals; one training seed per model.
- Both held-out sets are now used (v1 once per model; v2 once per condition). Model work is stopped; any further model change needs a new held-out set.
- All external actions are mocked. The checker's guarantees cover only rules C1-C8, under the trust assumptions in `spec/SPEC.md` section 5.
