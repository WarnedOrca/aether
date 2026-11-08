# Job spec dev split

- `requests.jsonl`: 60 requests (30 ordinary, 11 ambiguous, 13 traps, 6 unsupported), same row format as `eval/heldout4/`.
- Hand-written by Claude (an AI assistant) on 2026-11-08. **Evaluation only, never training data.** Used for all decisions: the regex baseline gate, the epoch choice, any debugging.
- SHA-256 at creation: `651e1e085001dcc764a3637c9c649a6f85e33a14fe509e9f13a0f6f461107079` (not frozen; changes must be logged in HANDOFF.md).
