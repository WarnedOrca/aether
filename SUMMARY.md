# Aether sessions 5-6: 2026-10-29, the one-time held-out v3 run of v0.2 (and a wording review)

**Outcome: the released model v0.2 solves 18 of 72 brand-new tasks (95% CI 0.16-0.36) by itself, and 22 of 72 with checker feedback. The base model solves 2.** This is a modest result, in line with the earlier held-out sets. No statistical test was run, because the test declared in advance needed a 7B model and none was included (none beat v0.2 on dev). Nothing says the model is safe. The only claim is about the checker: the programs it accepted caused 0 monitor problems.

## Final held-out v3 table (72 tasks: 36 ordinary, 36 traps; 18 new business types)
Sources: `eval/results/stage5/summary.json`, `eval/results/stage5/report.json`.

| System | Correct /72 (95% CI) | Ordinary /36 (95% CI) | Traps /36 (95% CI) | Parses | Rejected by checker | Rule-violating programs that executed |
|---|---|---|---|---|---|---|
| Base 1.5B + 3 examples | 2 (0.01-0.10) | 2 (0.02-0.18) | 0 (0.00-0.10) | 32% | 18 | 0 |
| **v0.2 plain (released)** | **18 (0.16-0.36)** | **13 (0.23-0.52)** | **5 (0.06-0.29)** | 81% | 25 | **0** |
| v0.2 with checker feedback | 22 (0.21-0.42) | 14 (0.25-0.55) | 8 (0.12-0.38) | 79% | 20 | 0 |

- **Statistical tests: none.** The only test declared before any v3 run was "the 7B model chosen on dev vs v0.2 plain". You excluded every 7B adapter, and you said not to add new comparisons, so there is no McNemar test and no adjusted p-value. All rows are descriptive and exploratory. Overlapping intervals mean the table does not show that feedback beats plain.
- **What the checker did:** it rejected 18, 25 and 20 programs, and every program it accepted ran with 0 monitor problems.
- **Post-hoc tests (added later, exploratory, not declared before the run, no adjustment for doing two tests; `eval/results/stage5-posthoc.json`):** base vs v0.2 plain, 2 vs 18 correct, exact McNemar p = 0.00014; v0.2 plain vs with feedback, 18 vs 22 (feedback fixed 4 tasks and broke none), p = 0.125, which is **not** significant. So there is no evidence here that feedback helps; v0.2 clearly solves more than the base model, but that test was chosen after seeing the results.

## What was done
1. **Pre-flight:** 336 tests passed and held-out v3 validated (72 tasks, 0 problems, frozen hashes unchanged). The 1.5B base model has a reviewed Apache-2.0 lock entry. The v0.2 adapter is byte-identical to the released one. Offline loading was checked on 2 development tasks.
2. **Last changes, no model change:** the README, `docs/RESULTS.md` and the model card template now include the three negative 7B experiments (dev only), each number tied to its result file. Inference settings were not changed: on dev, extra feedback rounds fixed nothing beyond the first.
3. **Freeze:** the conditions file (base, v0.2 plain, v0.2 with feedback; no 7B) was committed before the run, and its hash, the adapter's and the held-out files' are recorded in `HANDOFF.md`. Stage 5 can now resume after a crash without generating any task twice (tested). It was not needed: the run finished in 27 minutes without a crash.
4. **Run:** each condition was run once, and nothing was changed after seeing results.

**Held-out v3 is now used.** Any later model change needs a new frozen held-out set first.

## Session 6: wording review (no new runs except the post-hoc arithmetic)
- The diff of README, `docs/RESULTS.md` and the model card template since the last published commit (`b7a360d`) is in `docs/review/docs-diff-since-published-b7a360d.diff`.
- Toned down claims that were stronger than the data: "the checker blocked every program that broke a rule" (7 places) now says what the data shows, that accepted programs caused 0 monitor violations on generated test data; "beat the base model", "worse on new SOPs" and "from 0 to a useful level" now give the counts and whether a test was significant; the 7B notes now say "reads or writes" (the counts include writes), give the measured parse range, and no longer say the counterfactual data "cut" errors (one run each, not a tested effect).
- The column "unsafe programs reaching execution" is now "rule-violating programs that executed" in the write-ups (the JSON field in the committed result files keeps its old name, because results were not changed).

## Session 7 (2026-11-01): personal data removed, then published to GitHub
- You chose "scrub, then push". Your user folder and the lists of running desktop programs were removed from all 53 unpublished commits before anything went public; no number changed (checked automatically), all 339 tests pass, and the push was a normal one. The old local history is kept as branch `backup/pre-scrub-2026-11-01` (never pushed).

### Before the scrub
- The pre-publish scan found **personal data** in the 52 unpublished commits: your Windows user folder (`<home>`) in 16 files, and the list of desktop programs that were running (names not repeated here) in several committed result files. No secrets, tokens or real email addresses were found, and nothing is too large. As instructed, I stopped: **nothing was pushed and nothing was uploaded to Hugging Face.**
- Fixed one number: the post-hoc base-vs-v0.2 p-value is 0.00014 (it was written as 0.00015). Also removed the word "guarantees" from `docs/RESULTS.md`.
- Hugging Face is not logged in on this machine, so the model card upload needs you anyway. The card is built and ready in `dist/model/README.md`; its numbers match the README.

## What is live now (checked by fetching the public pages)
- **GitHub:** commit `6fb1215` is on `main`; the public README matches the local one exactly (held-out v3 18/72, post-hoc p = 0.00014), and the published logs contain no user folder or program names.
- **GitHub Pages:** the demo site is up and shows no result numbers, so it cannot disagree with the README.
- **Hugging Face:** the model card was **not** updated (not logged in on this machine); it still shows the earlier text.

## Needs you
1. Upload the model card yourself: rebuild, log in, then one `hf upload` command that sends only the card (exact commands in `HANDOFF.md`, Session 7).
2. Optionally delete the local backup branch `backup/pre-scrub-2026-11-01`.
3. This summary update is a local commit; push it when convenient.
4. A new frozen held-out set is needed before any further model change.

Nothing was uploaded to Hugging Face, and nothing was installed, bought or signed in to. Left alone: `pyproject.toml`, `uv.lock`, `data/synthetic_v4_smoke/`.
