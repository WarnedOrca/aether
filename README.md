# Aether

An original programming language for **verifiable business procedures**, plus a small fine-tuned open model that compiles plain-English SOPs into Aether programs.

**What it is:** an open benchmark, a small model, and a checker. It is not a new safety paradigm. The checker verifies a fixed set of named rules for this language only; see `spec/SPEC.md` sections 5 and 13.

**Main contribution: the checker.** In every evaluation, the programs the checker accepted had 0 monitor violations when run on generated test data. The released model (v0.2) solves only 6/30 held-out trap tasks by itself. Neither the model nor the system should be called "safe"; the narrow claim is that the checker verifies rules C1-C8 for Aether programs.

## Links

- Code: https://github.com/WarnedOrca/aether
- Model (v0.2 LoRA): https://huggingface.co/sidchalamala/aether-coder-1.5b-lora
- Synthetic training data: https://huggingface.co/datasets/sidchalamala/aether-sop-programs
- Benchmark and held-out trap set: https://huggingface.co/datasets/sidchalamala/aether-benchmark
- Demo (checker and interpreter in your browser; the model is not hosted): https://warnedorca.github.io/aether/
- Local demo with the model tab: `uv run --group demo python demo/app.py`

## Results

"Correct" = passes the checker AND has the same effects as the reference program on generated test data (scorer field `safe_and_correct`; it is not a safety rating). Single runs, greedy decoding. Details: [docs/RESULTS.md](docs/RESULTS.md); how to reproduce: [docs/REPRODUCE.md](docs/REPRODUCE.md).

**Final evaluation: frozen held-out trap set** (30 tasks, 10 new business types; frozen before any trap training data existed; each model evaluated once):

| System (Qwen2.5-Coder-1.5B-Instruct base) | Correct | 95% CI |
|---|---|---|
| Base model, reference card + 3 examples | 0/30 | 0.00-0.11 |
| v0.1 LoRA (synthetic data) | 6/30 | 0.10-0.37 |
| **v0.2 LoRA (+ 413 trap samples), released** | **6/30** | 0.10-0.37 |

Negative result: the 413 targeted trap samples did not improve held-out performance (v0.2 vs v0.1: 6 vs 6, paired exact McNemar p = 1.0). Both LoRAs solved more tasks than the base model (6 vs 0, paired exact McNemar p = 0.031). Novel trap types absent from training: 0/4 for all.

**Held-out v2** (90 tasks, 30 traps, 15 new business types; frozen before any v0.3 training; each condition run once; plan pre-registered):

| System | Correct (of 90) | 95% CI | Traps (of 30) |
|---|---|---|---|
| Base model, reference card + 3 examples | 1 | 0.00-0.06 | 0 |
| **v0.2 plain, released** | **20** | 0.15-0.32 | 2 |
| v0.2 with checker feedback (exploratory) | 22 | 0.17-0.34 | 2 |
| v0.2 grammar-constrained (exploratory) | 19 | 0.14-0.31 | 2 |
| v0.3 plain, not released (exploratory) | 14 | 0.10-0.24 | 3 |
| v0.3 with checker feedback, not released (pre-registered primary) | 15 | 0.10-0.26 | 3 |
| v0.3 grammar-constrained, not released (exploratory) | 15 | 0.10-0.26 | 3 |

Pre-registered primary comparison, **null result:** v0.3 with checker feedback vs v0.2 plain, 15 vs 20, paired exact McNemar p = 0.33. v0.3 (more varied generated data) is an unreleased negative result: 100/100 on its synthetic test (as v0.2 is), but fewer held-out v2 tasks solved than v0.2 (14 vs 20 plain; the pre-registered test above was not significant). "With checker feedback" = up to 3 retries that see parser and checker errors; always reported separately from plain output. Details: [docs/RESULTS.md](docs/RESULTS.md).

**Held-out v3** (72 tasks, 36 traps, 18 new business types; the one-time final run of the released v0.2, 2026-10-29; each condition run once): base model with 3 examples 2/72 (95% CI 0.01-0.10); **v0.2 plain 18/72** (0.16-0.36; 13/36 ordinary tasks, 5/36 traps); v0.2 with checker feedback 22/72 (0.21-0.42). No confirmatory test was run (the declared comparison needed a 7B model; none beat v0.2 on dev). Post-hoc and exploratory only (not declared before the run): base vs v0.2 plain, exact McNemar p = 0.00015; v0.2 plain vs with feedback, p = 0.125 (not significant); `eval/results/stage5-posthoc.json`. The checker's accepted programs caused 0 monitor problems. Source: `eval/results/stage5/`.

**Development benchmark: 110 tasks, used during development** (scorer design, SOP wording, and model comparison, so not a clean test): base with 3 examples 3/110; v0.1 30/110; v0.2 34/110 (v0.2 vs v0.1 p = 0.48).

**Limitations:** all benchmark and held-out tasks were drafted by Claude (an AI assistant), not taken from real businesses. The training English is templated. Evaluation sets are small, with wide intervals, and there is one seed per model. All external actions are mocked.

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

## Idea

1. A business owner writes a procedure in English.
2. A small model turns it into an Aether program.
3. A static checker verifies safety rules (approval before customer-facing actions, spending/refund limits, data-access boundaries).
4. The owner reads a plain-English rendering of what will happen.
5. The program runs in a sandbox with a full audit log. External actions (email, sheets, calendar) are mocked.

## Quick start

Needs [uv](https://docs.astral.sh/uv/). Everything runs locally; nothing contacts a real service.

```bash
uv sync
uv run pytest                                   # full test suite
uv run python -m checker data/examples/ProcessReturn.ae --render
uv run python eval/run_properties.py --seeds 100  # property tests at scale -> eval/results/
```

## Layout

| Folder | Purpose |
|---|---|
| `spec/` | Language specification (`SPEC.md`) |
| `checker/` | Parser and static safety checker |
| `interpreter/` | Sandboxed interpreter, mock connectors, audit log |
| `data/` | Training and test data (programs + SOPs) |
| `eval/` | Benchmark and scoring scripts |
| `training/` | Fine-tuning scripts (free GPUs only) |
| `docs/` | Plans, notes, write-ups |

## Constraints

- $0 budget: free tiers and open-weight models only.
- No invented numbers or citations.
- Human approval before any customer-facing action.

## License

Code: Apache-2.0 (`LICENSE`). Synthetic dataset, benchmark, and held-out set: CC-BY-4.0 (see their cards in `release/templates/`). The benchmark and held-out tasks were drafted by Claude (an AI assistant), not taken from real businesses.
