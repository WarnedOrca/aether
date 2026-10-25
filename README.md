# Aether

An original programming language for **verifiable business procedures**, plus a small fine-tuned open model that compiles plain-English SOPs into Aether programs.

**What it is:** an open benchmark, a small model, and a checker. It is not a new safety paradigm. The checker verifies a fixed set of named rules for this language only; see `spec/SPEC.md` sections 5 and 13.

**Main contribution: the checker.** In every evaluation, the checker blocked every program that broke a rule, and the programs it accepted had 0 monitor violations. The released model (v0.2) solves only 6/30 held-out trap tasks by itself. Neither the model nor the system should be called "safe"; the narrow claim is that the checker verifies rules C1-C8 for Aether programs.

## Results

"Correct" = passes the checker AND has the same effects as the reference program on generated test data (scorer field `safe_and_correct`; it is not a safety rating). Single runs, greedy decoding. Details: [docs/RESULTS.md](docs/RESULTS.md); how to reproduce: [docs/REPRODUCE.md](docs/REPRODUCE.md).

**Final evaluation: frozen held-out trap set** (30 tasks, 10 new business types; frozen before any trap training data existed; each model evaluated once):

| System (Qwen2.5-Coder-1.5B-Instruct base) | Correct | 95% CI |
|---|---|---|
| Base model, reference card + 3 examples | 0/30 | 0.00-0.11 |
| v0.1 LoRA (synthetic data) | 6/30 | 0.10-0.37 |
| **v0.2 LoRA (+ 413 trap samples), released** | **6/30** | 0.10-0.37 |

Negative result: the 413 targeted trap samples did not improve held-out performance (v0.2 vs v0.1: 6 vs 6, paired exact McNemar p = 1.0). Both LoRAs beat the base model (p = 0.031). Novel trap types absent from training: 0/4 for all.

**Development benchmark: 110 tasks, used during development** (scorer design, SOP wording, and model comparison, so not a clean test): base with 3 examples 3/110; v0.1 30/110; v0.2 34/110 (v0.2 vs v0.1 p = 0.48).

**Limitations:** all benchmark and held-out tasks were drafted by Claude (an AI assistant), not taken from real businesses. The training English is templated. Evaluation sets are small, with wide intervals, and there is one seed per model. All external actions are mocked.

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
