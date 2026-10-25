# Results (2026-10-25)

Published artifacts: model https://huggingface.co/sidchalamala/aether-coder-1.5b-lora, data https://huggingface.co/datasets/sidchalamala/aether-sop-programs, benchmark and held-out set https://huggingface.co/datasets/sidchalamala/aether-benchmark, code https://github.com/WarnedOrca/aether.

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
- **Blocking rule-breaking programs is the checker's job, not the model's.** In every evaluation, the checker blocked every program that broke a rule, and programs it accepted had 0 monitor violations. The model by itself solves 6/30 held-out traps.
## Limitations

- All benchmark and held-out tasks were drafted by Claude (an AI assistant), not taken from real businesses.
- The training English is templated (rule-based generator). Most held-out failures are general errors on unfamiliar businesses.
- Small evaluation sets with wide intervals; one training seed per model.
- The held-out set is now public and has been used once per model. Any future model change needs a new held-out set.
- All external actions are mocked. The checker's guarantees cover only rules C1-C8, under the trust assumptions in `spec/SPEC.md` section 5.
