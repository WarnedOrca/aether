# What the business-workflow agent can do today (updated 2026-11-08, with the draft pack tool)

Read this before talking to any business. Everything below was checked against the code and the result files on 2026-11-08. If something here stops being true, update this page before using the outreach kit.

## New: the draft pack tool (`tool/draft-pack.html`)

This is the part an owner can use for real today. It is one web page that runs entirely in the owner's browser, with no install and no internet connection. The owner loads their **own** customer list (a CSV export from their spreadsheet or booking app) on **their own computer**. The page prepares one draft per customer who is due (appointment reminder, follow-up, review request or invoice reminder). It applies the owner's rules: opted-out customers are always skipped, as is anyone contacted in the last N days. It only offers send links during the owner's sending hours, and it stops at a daily limit of at most 200. Rows with missing or malformed contact details, unclear opt-out values or unreadable dates are listed with the reason instead of being guessed. The owner approves or skips each draft and **sends the approved ones from their own phone or email** using a copy button or an `sms:`/`mailto:` link.

- It never sends anything itself, never uploads anything, and keeps nothing after the tab is closed (its security policy blocks all network connections).
- The student never needs to see the customer list: the owner runs it on their own machine.
- It does **not** run Aether programs. The rule checks are plain JavaScript, tested in `tests/test_tool.py`.
- Whether it saves time for a given owner is unknown until measured (`MEASURING-IMPACT.md`; the page has an optional stopwatch that writes a pilot-log row and never estimates time saved).

How to try it: `tool/README.md`.

## The Aether side: the short version

Today the agent can take one repeated task a business owner describes in plain English and turn it into a short Aether program. The checker then verifies the program against the owner's rules, and it can be run against **made-up sample rows** so the owner sees, in plain English, exactly which messages it would draft and which changes it would make.

It **cannot yet touch a real business system.** It does not read a real Google Sheet, booking app or inbox, and it never sends a real text, email, refund or order. Every connector is a mock: the "outbox" is a file on the student's computer. So a pilot today can produce a checked plan, a dry run on sample data, and an honest "before" measurement of the task. It cannot save the owner any time until a real connector exists (see "Next build step").

The only claim to make about safety: the checker verifies core rules C1-C8 for programs in the Aether language (`spec/SPEC.md`, sections 5 and 13), and in every evaluation the programs it accepted caused 0 monitor violations on generated test data. Never call the agent, the model or the system "safe".

## What exists and runs

| Part | What it does | Evidence |
|---|---|---|
| Checker (`python -m checker <file> --render`) | Parses an Aether program, rejects it if it breaks one of the core rules (for example, a customer message without the owner's approval, an unlisted column, a refund over the cap), and prints a plain-English description with a safety summary | 339 tests pass (2026-11-08); 88 of 88 rule-breaking mutants rejected (`eval/results/properties-2026-10-24.json`) |
| Plain-English rendering | Shows the owner, step by step, what the program will do, plus every cap, the approval mode, the allowed sending hours and the exact columns it may read | Run on `data/examples/ProcessReturn.ae` on 2026-11-08 |
| Interpreter + independent monitor | Runs a checked program against mock sheets, a mock outbox and a mock money ledger; a separate monitor compares what happened with what the owner approved | 25,000 generated cases, 0 violations (same result file); a dry run of `data/examples/AppointmentReminders.ae` on made-up rows finished with status `ok` and 0 monitor problems (2026-11-08) |
| Draft pack tool (`tool/draft-pack.html`) | Offline drafts from the owner's own CSV, the owner's rules, approve or skip each, send from the owner's own apps | Tests in `tests/test_tool.py` (made-up rows only) |
| Browser demo | Checker and interpreter in the browser, mock data only, no model | https://warnedorca.github.io/aether/ |
| Model v0.2 (1.5B LoRA) | Drafts a program from an owner's English description | Correct on 18 of 72 brand-new held-out tasks (`eval/results/stage5/summary.json`). It is wrong most of the time, so every draft must be read and fixed by a person |
| Local demo app (`demo/app.py`) | Same as the browser demo, plus a model tab | Does not start on this machine today: the `gradio` package is not installed (adding it is the owner's call) |

The 15 example procedures in `spec/SPEC.md` (section 10) show the kinds of tasks that fit: appointment reminders, no-show follow-ups, reservation confirmations, low-stock reorder requests, small refunds within a limit, back-in-stock emails, rebooking nudges, service reminders, late-tuition notes, filling a cancelled slot from a waitlist. Every customer-facing step waits for the owner's approval, and every money step has a hard cap the owner sets.

## What it does not do yet

- Connect to anything real: no Google Sheets, Square, Calendly, Gmail, SMS provider or bank (the draft pack works from a CSV the owner exports, and the owner does the sending). Real connectors are listed as future work in `spec/SPEC.md` (section 5, "What the checker does NOT guarantee").
- Send anything. Messages, refunds and orders are written to mock files.
- Read replies from customers (out of scope for v1).
- Write correct programs on its own. The model is a starting point; the student writes or fixes the program and the owner reads the rendering.
- Run on its own schedule somewhere. Nothing is hosted; it runs when the student runs it.
- Handle data the owner did not describe: it reads only the columns the owner's policy lists.

## What a business would need to give

To use the draft pack, the owner needs only their own CSV export, on their own computer; nothing has to be given to the student. For the first conversation and an Aether dry run, **no customer data at all**:

1. A description of one repeated task: what triggers it, what gets sent or changed, to whom.
2. The column names of the sheet or app export they use (names only, not the rows).
3. Their rules: who may be contacted, which fields must never appear in a message (for example health notes or card details), money limits if any, allowed sending hours, and whether they want to approve each message or a batch.
4. Their own estimate of how long the task takes and how often it happens (this becomes the "before" measure; see `MEASURING-IMPACT.md`).

The student then builds made-up rows with the same columns. Real rows are not needed until a real connector exists, and then only with the written permission described in `pilot-agreement-template.md`.

## What could go wrong

| Risk | Why it can happen | What limits it |
|---|---|---|
| The program does the wrong thing even though it passes the checker | The checker verifies the rules, not that the program matches what the owner meant (`spec/SPEC.md`, section 5) | The owner reads the plain-English rendering and the dry-run results before anything else happens |
| A message goes to the wrong person | Sheet contents are trusted; a wrong phone number is still "from an allowed column" | Today nothing is sent at all; later, the owner approves each message and can see the recipient |
| Customer data leaks | The student receives real data, or a private field is put in a message | No real data in this phase; private columns marked `deny reveal` are rejected by the checker if they appear in a message |
| The owner stops reading approvals | Approving many messages is tedious; a batch preview shows samples, not every message | Start with per-message approval and small volumes |
| The pilot costs the owner more time than it saves | Meetings, reviewing renderings, fixing data | Keep the first conversation to 10 minutes; one task only; the owner can stop at any time |
| Mock behaviour differs from a real connector later | Real systems have quirks the mocks do not | Test any real connector on a copy of the sheet first |
| Results get overstated | Wanting a strong Common App entry | Only measured, dated, owner-approved numbers count (`MEASURING-IMPACT.md`) |
| Sensitive businesses | Health, legal, children's or payment data raise the stakes | Prefer a first pilot without these |

## Next build step (owner's decision)

Before any pilot can save real time, a draft-only connector has to be built and reviewed: for example a small Google Apps Script that runs inside the business's own Google account, reads only the allowed columns, and writes **drafts** (or a "to send" tab) that the owner sends themselves. The plan is in the vault (`Agent/Outreach and Architecture.md`). Nothing of it is built yet.
