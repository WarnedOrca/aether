---
license: apache-2.0
base_model: Qwen/Qwen2.5-Coder-1.5B-Instruct
library_name: peft
tags: [lora, code, dsl, aether]
---

# Aether SOP-to-program LoRA v0.2 (Qwen2.5-Coder-1.5B-Instruct)

A LoRA adapter that turns a plain-English business procedure, plus the owner's policy and sheet list, into an Aether program. **The model is not a safety mechanism.** Every program it writes must pass the Aether checker before it runs. The checker blocks programs that break the policy's rules; the model often writes such programs.

**Links:** browser demo of the checker and interpreter (the model is not hosted there): https://warnedorca.github.io/aether/ · code: https://github.com/WarnedOrca/aether · benchmark and held-out set: https://huggingface.co/datasets/sidchalamala/aether-benchmark

"correct" below means passes the checker and has the same effects as the reference program (scorer field `safe_and_correct`). It is not a safety rating.

## Final evaluation: frozen held-out trap set (30 tasks, each model evaluated once)

Each task asks for something the policy forbids or Aether cannot do. The correct answer is a program that does the permitted alternative. The set was frozen before any trap training data existed and was never used for training or decisions.

| System | Correct | 95% CI |
|---|---|---|
| Base model + reference card + 3 examples | {h_base}/30 | {h_base_lo}-{h_base_hi} |
| v0.1 (synthetic data only) | {h_v1}/30 | {h_v1_lo}-{h_v1_hi} |
| **v0.2 (this adapter: + {n_traps} trap samples)** | **{h_v2}/30** | {h_v2_lo}-{h_v2_hi} |

- **Negative result:** adding {n_traps} targeted trap samples did **not** improve held-out performance. v0.2 vs v0.1: {h_v2} vs {h_v1}, paired exact McNemar p = {p_v2_v1}.
- v0.2 vs the base model: p = {p_v2_base}.
- Novel trap types absent from all training data (delete rows, raise a limit): 0/4 for every system.
- In every evaluation, the programs the checker accepted had 0 monitor violations when run on generated test data. The model by itself solves {h_v2}/30 held-out traps.

## Held-out v2 (90 tasks, 30 traps, 15 new business types; each condition run once)

A second frozen set, written and hashed before any v0.3 training or tuning. Same scorer. 95% Wilson intervals.

| System | Correct (of 90) | 95% CI | Traps (of 30) |
|---|---|---|---|
{v2_rows}

- **Pre-registered primary comparison (null result):** v0.3 with checker feedback vs this adapter (v0.2) plain: {v2_pa} vs {v2_pb}, paired exact McNemar p = {v2_pp}. The new data plus checker feedback did **not** improve on v0.2.
- v0.2 plain vs the base model: {v2_v2} vs {v2_base} (paired p = {v2_p_base}; this test was not pre-registered).
- Everything else in this table is exploratory. "With checker feedback" means up to 3 extra attempts in which the model sees the parser and checker errors; it is reported separately from plain output. "Grammar-constrained" means decoding restricted to tokens the Aether grammar allows.
- **v0.3 is not released.** It is a negative result: it adds 1,232 generated samples from 30 more business types, scores 100/100 on its synthetic test split (as v0.2 does), and solves fewer held-out v2 tasks than v0.2 (not significant in the pre-registered test), which may suggest the generated data teaches the generator's templates more than reading real SOPs.

## Held-out v3 (72 tasks, 36 traps, 18 new business types; the one-time final run of this adapter)

**Held-out v3** (72 tasks, 36 traps, 18 new business types; the one-time final run of the released v0.2, 2026-10-29; each condition run once): base model with 3 examples 2/72 (95% CI 0.01-0.10); **v0.2 plain 18/72** (0.16-0.36; 13/36 ordinary tasks, 5/36 traps); v0.2 with checker feedback 22/72 (0.21-0.42). No confirmatory test was run (the declared comparison needed a 7B model; none beat v0.2 on dev). Post-hoc and exploratory only (not declared before the run): base vs v0.2 plain, exact McNemar p = 0.00014; v0.2 plain vs with feedback, p = 0.125 (not significant); `eval/results/stage5-posthoc.json`. The checker's accepted programs caused 0 monitor problems. Source: `eval/results/stage5/`.

| System | Correct (of 72) | 95% CI | Ordinary (of 36), 95% CI | Traps (of 36), 95% CI | Parse rate |
|---|---|---|---|---|---|
{v3_rows}

- Feedback's 22 vs plain's 18 was not a pre-declared test. The two post-hoc tests above are exploratory: chosen after seeing the results, with no multiple-comparison adjustment.
- Programs the checker accepted caused 0 monitor violations on generated test data.

## Development benchmark (110 tasks, used during development)

This benchmark was used to build the scorer and compare models during development, so treat it as a development set, not a clean test.

| System | Correct | Traps (30) |
|---|---|---|
| Base model + reference card + 3 examples | {d_base}/110 | 0 |
| v0.1 | {d_v1}/110 | {d_v1_traps} |
| **v0.2** | **{d_v2}/110** | {d_v2_traps} |

v0.2 vs v0.1: paired p = {p_dev}.

## Larger-model experiments (7B, development benchmark only): negative results

After v0.2, three QLoRA adapters on Qwen2.5-Coder-7B-Instruct were trained on new data whose English was written by a locally run open model (Qwen2.5-7B-Instruct) from script-made programs. None was better than v0.2 on the 110-task development benchmark, so **none was released and none was evaluated on a held-out set.** Same scorer, greedy decoding, paired exact McNemar against v0.2 (34/110).

| Adapter (7B) | Training data | Correct /110 (epoch 1, epoch 2) | p vs v0.2 (epoch 2) | Source |
|---|---|---|---|---|
| q7b-v1 | 898 local-model wordings of 515 programs | 26, 30 | 0.60 | `eval/results/compare-dev-v0.2-vs-q7b-epoch*-2026-10-26.json` |
| q7b-v2 | 2,401 wordings of 1,519 programs (mislabelled trap rows removed) | 32, 32 | 0.85 | `eval/results/dev-report-q7b-v2-2026-10-27.json` |
| q7b-v3 | q7b-v2 data + 950 rows where the obvious column is not allowed | 29, 33 | 1.0 | `eval/results/dev-report-q7b-v3-session4.json` |

- With checker feedback on dev (exploratory): q7b-v2 epoch 2 35/110 and q7b-v3 epoch 2 36/110, against v0.2 36/110 (p = 1.0 both; `eval/results/dev-repair-compare-2026-10-28.json`, `eval/results/dev-repair-compare-session4.json`).
- The 7B adapters' output parses more often (94.5-98.2% of the 110 tasks, against 78.2% for v0.2), but more of it reads or writes columns the policy does not allow (21-25 of 110 for q7b-v1 and q7b-v2, against 3 for v0.2) or does the wrong thing. q7b-v3, trained with programs where the obvious column is not allowed, had 13 such errors (q7b-v2: 25) and 33/110 correct (q7b-v2: 32); with one training run each, neither difference is a tested effect.
- In all of these runs, the programs the checker accepted caused 0 monitor problems.

## Training

The v0.1 recipe (LoRA rank {rank}, learning rate {lr}, {epochs} epochs, seed 42; only the program tokens are trained) on {n_train} verified examples: {n_base} synthetic plus {n_traps} trap-style. Training took {minutes} minutes on one {gpu}, at $0. The checkpoint was chosen by validation loss.

## Limitations

- Trained on templated synthetic English only. Most held-out failures are general errors on unfamiliar businesses (parse errors, type errors, reading columns the policy does not allow), not only trap-following.
- All benchmark and held-out tasks were drafted by Claude, an AI assistant, not taken from real businesses.
- Small evaluation sets with wide intervals; one training seed per model.
- Aether's external actions (messages, money, calendars) are mocked. This is research software.
- Do not describe this model, or Aether as a whole, as "safe". The narrow claim is that the checker verifies the named rules C1-C8 for Aether programs (see the specification).

Provenance clarification: the older rule-based generator's template sentences in `data/gen/*.py` were typed by Claude Code, an AI coding assistant. Script execution produced the older training examples, but their English templates were AI-authored. The owner has decided that stage 4 will train only on `data/synthetic_v4`, whose wordings come from a locally run open-weight model. This note changes no published results.
