# AI dev check (author-written, development only, not an independent test)

Requests: `eval/jobspec-ai-dev/requests.jsonl`, 64 sentences across 20 business types (32 ordinary, 12 ambiguous, 12 traps, 8 unsupported), written by Claude. Model: Qwen/Qwen2.5-7B-Instruct (locked revision, 4-bit, run locally). Scoring rules: `docs/jobspec/DESIGN.md` ("Evaluation plan").

| Round | Keyword rules | Local model | Model + keyword fallback (what ships) | Writer: wordings passing the checks |
|---|---|---|---|---|
| v1 prompts (`summary-interpret-v1.json`) | 50/64 (0.67-0.87) | 44/64 (0.57-0.79) | 45/64 (0.58-0.80) | 32/69 attempts (0.35-0.58); 10 of 12 cases reached 3 wordings |
| v2 prompts (`summary-interpret-v2.json`) | 50/64 (0.67-0.87) | 61/64 (0.87-0.98) | 61/64 (0.87-0.98) | 33/83 attempts (0.30-0.51); 9 of 12 cases reached 3 |

Intervals are 95% Wilson. With and without checker validation gave the same counts in every row.

- **v2 was written after reading the v1 errors on these same 64 sentences.** Its 61/64 is therefore optimistic and says nothing about wording the author did not write. Most v1 misses came from two systematic mistakes. The model treated "the day before/after" as the days-since-contact rule (15 of the 21 wrong specs), and it filled unstated sending hours with 00:00-23:59 (4). v2 states the defaults explicitly.
- Model + fallback vs keyword with v2 prompts: 14 items only the model got right, 3 only the keyword rules (exact McNemar p = 0.0127). This is descriptive, because the prompt was tuned on this set.
- The writer v2 prompt was not better than v1, so **writer-v1 stays the default**. Its main failures were outputs with no usable `text`, repeated wordings, and blocked claim words.
- Neither interpreter has been tested on independent (real owner) wording.
