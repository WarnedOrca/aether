# Aether: instructions for AI coding assistants

Personal project notes (if any) live in `CLAUDE.local.md`, which is not published.

## Hard constraints
- Budget is $0. No paid APIs, GPUs, or services. Free tiers and open-weight models only.
- Never invent numbers, citations, or results. Every reported number comes from a committed result file in `eval/results/`.
- Explain each design decision briefly, in plain language.
- Small, tested steps. Do not install anything or change settings without saying what and why first.
- Human approval before any customer-facing action; all external actions are mocked.
- Python via `uv` only (`uv sync`, `uv run pytest`).
- The held-out trap set (`eval/heldout/`) is frozen: never use it for training, tuning, or design decisions.

## Layout
`spec/` language spec, `checker/` parser and checker, `interpreter/` sandbox runtime, `data/` synthetic data, `eval/` benchmark and scoring, `training/` fine-tuning, `release/` and `demo/` publishing, `docs/` results and reproduction.
