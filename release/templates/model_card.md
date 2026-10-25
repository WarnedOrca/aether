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
- In every evaluation, the checker blocked every program that broke a rule, and programs it accepted had 0 monitor violations. The model by itself solves {h_v2}/30 held-out traps.

## Development benchmark (110 tasks, used during development)

This benchmark was used to build the scorer and compare models during development, so treat it as a development set, not a clean test.

| System | Correct | Traps (30) |
|---|---|---|
| Base model + reference card + 3 examples | {d_base}/110 | 0 |
| v0.1 | {d_v1}/110 | {d_v1_traps} |
| **v0.2** | **{d_v2}/110** | {d_v2_traps} |

v0.2 vs v0.1: paired p = {p_dev}.

## Training

The v0.1 recipe (LoRA rank {rank}, learning rate {lr}, {epochs} epochs, seed 42; only the program tokens are trained) on {n_train} verified examples: {n_base} synthetic plus {n_traps} trap-style. Training took {minutes} minutes on one {gpu}, at $0. The checkpoint was chosen by validation loss.

## Limitations

- Trained on templated synthetic English only. Most held-out failures are general errors on unfamiliar businesses (parse errors, type errors, reading columns the policy does not allow), not only trap-following.
- All benchmark and held-out tasks were drafted by Claude, an AI assistant, not taken from real businesses.
- Small evaluation sets with wide intervals; one training seed per model.
- Aether's external actions (messages, money, calendars) are mocked. This is research software.
- Do not describe this model, or Aether as a whole, as "safe". The narrow claim is that the checker verifies the named rules C1-C8 for Aether programs (see the specification).
