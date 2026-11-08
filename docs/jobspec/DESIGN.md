# Job spec: design (2026-11-08)

## Why

The released v0.2 model writes a whole Aether program from an owner's request and is correct on 18 of 72 new held-out tasks (`eval/results/stage5/summary.json`). Most of what a small business needs from the draft pack is much narrower: pick one of four **tested** message jobs and fill in a few rules. So the model's job shrinks to producing a small JSON **job spec**. A deterministic compiler (`jobspec/compile.py`) turns the spec into (a) the config the draft pack page uses and (b) an Aether program that must pass the parser, the checker and a monitored dry run.

## The spec

Exactly one of:

```json
{"template": "follow_up", "channel": "sms", "min_days_since_contact": 7, "send_window": ["09:00", "20:00"], "daily_limit": 50}
{"refuse": "contact_opted_out"}
```

| Field | Values | Default when the request doesn't say |
|---|---|---|
| `template` | `appointment_reminder`, `follow_up`, `review_request`, `invoice_nudge` | (must be stated) |
| `channel` | `sms`, `email` | the template's channel: sms, except `invoice_nudge` = email |
| `min_days_since_contact` | integer 0-365: skip anyone contacted fewer than this many days ago | reminder 0, follow-up 7, review request 30, invoice 7 |
| `send_window` | `["HH:MM", "HH:MM"]`, 24-hour clock, start before end (no overnight sending) | `["09:00", "20:00"]` |
| `daily_limit` | integer 1-200 | 50 |
| `refuse` | `contact_opted_out`, `ignore_sending_hours`, `no_daily_limit`, `skip_owner_review`, `unsupported_job` | |

Rules that are **not** fields, because they can never be switched off: opted-out customers are always skipped; every message is drafted for the owner to approve and the owner sends it; the daily limit is at most 200.

The four templates (text in `jobspec/templates.json`, identical to the copy embedded in `tool/draft-pack.html`; a test checks this):

| Template | Who is due | Placeholders |
|---|---|---|
| `appointment_reminder` | date is 1 day ahead | name, business, date |
| `follow_up` | date was 1 day ago | name, business, date |
| `review_request` | date was 2 days ago | name, business, review_link |
| `invoice_nudge` | due date at least 1 day past (export unpaid invoices only) | name, invoice, amount, date |

## The compiler

`jobspec/compile.py` is deterministic (same spec, same output) and refuses any spec that fails `jobspec.spec.problems()` or is a refusal.

- `tool_config(spec)` returns the draft pack's `Core.build()` config.
- `aether_program(spec)` returns a policy and procedure: reads only the listed columns, contacts only the phone or email column, `limit sends <daily_limit> per day`, `send only between <window>`, a filter for "who is due", the opt-out condition and the days-since-contact condition, a loop `up to <daily_limit>`, a draft, `request approval`, `send`, and an `update` of `last_contacted`. On the Aether side only a blank or `no` opt-out value counts as "not opted out", which is stricter than the page.
- `dry_run(spec, rows)` parses, checks and runs the program on made-up rows under the independent monitor.

Tests (`tests/test_jobspec.py`): every template × channel compiles, passes the checker, and in a monitored dry run on made-up rows delivers exactly to the due rows and skips the opted-out, recently contacted and not-due rows, with 0 monitor violations; the daily limit appears in the program and caps deliveries; refusals and out-of-range specs are never compiled.

The only claim: programs the checker accepted caused 0 monitor violations on generated test data. Neither the model nor the tool is called "safe".
