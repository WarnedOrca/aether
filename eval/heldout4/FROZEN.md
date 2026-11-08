# Held-out set v4 (job spec requests): frozen

- File: `requests.jsonl`, 80 requests: 40 ordinary, 15 ambiguous (gold uses the documented defaults for anything not stated), 17 traps (texting opted-out customers, ignoring sending hours, no daily limit, skipping owner approval), 8 unsupported jobs. 40+ business types.
- Each row: `id`, `business`, `category`, `request`, `gold` (a job spec or a refusal), `safe_spec` for traps (the spec a safe redirect would give), `provenance`.
- **Hand-written by Claude (an AI assistant)** on 2026-11-08, not by real businesses. **Evaluation only: never training data, never paraphrased into training data**, never used for prompts, tuning, epoch choice or any decision.
- Frozen 2026-11-08, committed BEFORE the regex baseline, any training data generation or any model run for the job spec.
- SHA-256 requests.jsonl: `343dc938652adcdc256befa1bb238e2ec3be76439b532a1f15beb8b4eb2a3f4b`
- `tests/test_heldout_frozen.py::test_heldout4_unchanged` fails if the file changes.
- Every gold and safe_spec passes `jobspec.spec.problems()`. No request text is repeated between this set and `eval/jobspec-dev/`.
- Scoring rules, the confirmatory test and the pass margin are declared in `docs/jobspec/DESIGN.md` ("Evaluation plan").
- Each final condition is run exactly once (Step 7), from a committed conditions file.
