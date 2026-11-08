# Aether session 12: 2026-11-08, a draft pack tool a business owner can use, and the job spec

**Outcome: for this job, a model is not needed.** The plan was to shrink the model's task from writing a whole program to filling in a small JSON "job spec". A simple keyword/regex parser then cleared the bar declared in advance on the dev split (59/60 correct; every trap and unsupported request handled). By that pre-registered rule, no training data was generated, nothing was fine-tuned and the GPU was not used. What ships is a non-model tool: an offline page that drafts messages from the owner's own spreadsheet, with a one-sentence box that fills in the form.

## What was built
- **`tool/draft-pack.html`**: one offline web page (it cannot connect to the internet). The owner loads a CSV export of their customers, picks one of four jobs (appointment reminder, follow-up after a visit, review request, invoice reminder) and gets a draft for each customer who is due. Opted-out customers are always skipped (this can't be turned off). It also skips anyone contacted recently, keeps to the owner's sending hours and a daily limit (at most 200), and never guesses: unclear rows are listed as "not drafted" with the reason. The owner approves each draft and sends it from their own phone or email app. The page never sends anything. An audit log and an optional stopwatch (pilot-log columns, no time-saved estimate) can be downloaded.
- **One-sentence box**, for example "Email clients about overdue invoices between 9:30 and 16:30, at most 35 a day". "Fill in the form" sets the job, channel, days, hours and limit from the sentence using keyword rules, not AI. If the sentence asks to message opted-out customers, ignore sending hours, drop the limit, skip approval, or do something else (calls, social posts, charging cards), the form is left unchanged and the page says why.
- **`jobspec/`**: the job spec format, a deterministic compiler to the page's settings and to a checked Aether program (tested with a monitored dry run on made-up rows), and the regex parser (`jobspec/baseline.py`). Design and evaluation rules are in `docs/jobspec/DESIGN.md`.
- **Evaluation sets**: `eval/jobspec-dev/` (60 requests) and `eval/heldout4/` (80, frozen with a SHA-256 hash and a test). Both were hand-written by Claude, include ordinary, ambiguous, trap and unsupported requests, and are marked evaluation-only.

## How to try it (2 minutes, made-up data)
1. Open `tool/draft-pack.html` in Chrome, Edge or Firefox (double-click the file).
2. In step 1, load `tool/SAMPLE-DATA.csv` (10 made-up customers).
3. Optional: type "Remind customers by text the day before their appointment, from 9am to 6pm, at most 40 a day, and skip anyone contacted in the last week" and press **Fill in the form**. (Leave out the last part and Fake Customer D, contacted 3 days earlier, is drafted too, because reminders by default do not check recent contact.)
4. In step 3, set **Today's date** to 2026-12-01 and press **Prepare drafts for review**.
5. Expected result: 2 drafts (Fake Customer A and I) and 8 rows not drafted, each with a reason (opted out, bad phone number, contacted recently, not due, no phone, unclear opt-out value, unreadable date). Approve one: the "Open in Messages" link appears only inside your sending hours.

## Results (sources: `eval/results/jobspec/`)
| Set | System | Correct (95% Wilson) | Ordinary | Ambiguous | Traps | Unsupported |
|---|---|---|---|---|---|---|
| Dev (60) | regex parser, with and without checker validation | 59/60 (0.91-1.00) | 30/30 | 10/11 | 13/13 | 6/6 |
| Held-out v4 (80), run once | regex parser, with and without checker validation | 80/80 (0.95-1.00) | 40/40 | 15/15 | 17/17 (16 refused, 1 safe redirect) | 8/8 |

- **No statistical test.** The declared confirmatory test (fine-tuned model vs regex, exact McNemar) needed a model, and the gate said not to train one. It is reported as "not run".
- **Invalid outputs: 0.** On held-out v4, all 56 specs the parser produced (the non-refusals) compiled into Aether programs that the checker accepted. In a dry run on generated test data they caused 0 monitor violations. That is the only claim; neither the tool nor the parser is called safe.
- **A check outside the sets showed the weakness right away.** "Text patients the day before their appointment, only 9am to 6pm, at most 40 a day" is refused as "not one of the four jobs", because it never says "remind". "only 9am to 6pm" is also not read as sending hours, because the parser expects "from" or "between". Neither sentence is in the evaluation sets. The parser was left unchanged after the held-out run (run-once rule); only the page's example text was corrected. So expect misses on real wording.
- **Read these scores with care.** The same author (Claude) wrote the dev requests, the held-out requests and the regex. A perfect held-out score mainly shows that the sets are written in phrasing the regex already knows. Real owners will phrase things differently. That is why the page shows what it filled in and asks the owner to check every field, and why real (consented) owner sentences are the honest next test.

## What a business owner would actually experience
They export their customer list as a CSV and open one page on their own computer. Optionally they type one sentence describing the job, then press one button. They get a list of ready-to-send drafts plus a list of the customers it skipped and why. They read each draft, approve or skip it, and tap a link that opens the message in their own Messages or email app, where they press send. Nothing is uploaded and nothing is sent automatically. It does **not** connect to their booking app, read replies, or send on a schedule; the owner has to open the page each time. Whether this actually saves them time is unmeasured. The stopwatch exists so a pilot can measure it honestly.

## Proposed README wording (for your review; README and public docs were not edited)
> **Try the draft pack (no install, works offline).** Open `tool/draft-pack.html` and load your own customer CSV (or `tool/SAMPLE-DATA.csv`, made-up data). It drafts appointment reminders, follow-ups, review requests or invoice reminders; it always skips customers who opted out, respects your sending hours and a daily limit, and lists every row it skipped and why. You approve each message and send it from your own phone or email; the page never sends anything and never uploads your list. For this narrow job a keyword parser fills in the settings from one sentence; on our own evaluation sets it was correct on 59/60 dev and 80/80 held-out requests, but those sets were written by the same author as the parser, so real-world wording will do worse. Programs the checker accepted caused 0 monitor violations on generated test data.

## What I need from you
1. **Try the tool yourself** on the sample file (steps above), then tell me anything confusing.
2. **Decide on the README wording above** (accept, edit, or leave the README as it is). Nothing has been pushed.
3. **For a real test, real owner sentences.** With an owner's permission during a pilot, write down how they describe the job in their own words and keep it in `private/`. Do not invent any. That is the only way to know whether the one-sentence box helps real people.
4. Note: `pyproject.toml` and `uv.lock` show local modifications and there are untracked `website/`, `docs/website/` and two `eval/results/website-*` files. They are not from this session and I left them alone.

---

# Aether sessions 5-6: 2026-10-29, the one-time held-out v3 run of v0.2 (and a wording review)

**Outcome: the released model v0.2 solves 18 of 72 brand-new tasks (95% CI 0.16-0.36) by itself, and 22 of 72 with checker feedback. The base model solves 2.** This is a modest result, in line with the earlier held-out sets. No statistical test was run, because the test declared in advance needed a 7B model and none was included (none beat v0.2 on dev). Nothing says the model is safe. The only claim is about the checker: the programs it accepted caused 0 monitor problems.

## Final held-out v3 table (72 tasks: 36 ordinary, 36 traps; 18 new business types)
Sources: `eval/results/stage5/summary.json`, `eval/results/stage5/report.json`.

| System | Correct /72 (95% CI) | Ordinary /36 (95% CI) | Traps /36 (95% CI) | Parses | Rejected by checker | Rule-violating programs that executed |
|---|---|---|---|---|---|---|
| Base 1.5B + 3 examples | 2 (0.01-0.10) | 2 (0.02-0.18) | 0 (0.00-0.10) | 32% | 18 | 0 |
| **v0.2 plain (released)** | **18 (0.16-0.36)** | **13 (0.22-0.52)** | **5 (0.06-0.29)** | 81% | 25 | **0** |
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

## What is live now (checked by fetching the public pages, 2026-11-07)
- **GitHub:** commit `115241c` is on `main` (a normal push). The public README matches the local one exactly. It shows the held-out v3 results (base 2/72, v0.2 18/72, v0.2 with feedback 22/72) and the new checker sentence: "The checker rejects programs that break the policy's rules; in every evaluation, the programs it accepted caused 0 monitor violations on generated test data." The README, `docs/RESULTS.md` and the model card now all say "monitor violations".
- **GitHub Pages:** the demo site shows no result numbers, so it cannot disagree with the README.
- **Hugging Face:** the model card is live (you updated it through the website; model-repo commit `070b1c3`, "Update model card: held-out v3, 7B negative results, wording"). It shows the new checker sentence, the held-out v3 section (2/72, 18/72, 22/72) and the feedback test as not significant, and its text matches the locally built card.

## Needs you
1. Optionally delete the local backup branch `backup/pre-scrub-2026-11-01`.
2. A new frozen held-out set is needed before any further model change.

Claude uploaded nothing to Hugging Face (you updated the card yourself), and nothing was installed, bought or signed in to. Left alone: `pyproject.toml`, `uv.lock`, `data/synthetic_v4_smoke/`.
