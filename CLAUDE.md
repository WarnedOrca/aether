# Aether: instructions for AI coding assistants

Personal project notes (if any) live in `CLAUDE.local.md`, which is not published.

## Hard constraints
- Budget is $0. No paid APIs, GPUs, or services. Free tiers and open-weight models only.
- Never invent numbers, citations, or results. Every reported number comes from a committed result file in `eval/results/`.
- Explain each design decision briefly, in plain language.
- Small, tested steps. Do not install anything or change settings without saying what and why first.
- Human approval before any customer-facing action; all external actions are mocked.
- Python via `uv` only (`uv sync`, `uv run pytest`).
- Held-out discipline: every held-out set (`eval/heldout/`, `eval/heldout2/`, `eval/heldout3/`) is frozen (SHA-256 in its `FROZEN.md`) and never used for training, tuning, or design decisions. Freeze a new held-out set before any new training; tune only on the dev split; run each final condition once.
- Never call the model or the system "safe". The only claim is what the checker verifies (rules C1-C8).
- Training-data provenance: no text written by Claude, ChatGPT, or any other hosted AI may be used as training data. Allowed: human-written text, script-generated text, and text from open-weight models run locally (prefer Apache-2.0). Record the source of every training example.
- Do not push, publish, post, or change published numbers without the owner's review.
- Never ask for, read, or store passwords, tokens, or 2FA codes.
- Codex and other tools: see `AGENTS.md` and `HANDOFF.md`.

## Layout
`spec/` language spec, `checker/` parser and checker, `interpreter/` sandbox runtime, `data/` synthetic data, `eval/` benchmark and scoring, `training/` fine-tuning, `release/` and `demo/` publishing, `docs/` results and reproduction.
