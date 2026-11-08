# Draft pack (offline message drafts you send yourself)

`draft-pack.html` is one web page that helps a small-business owner with one repeated job: appointment reminders, follow-ups after a visit, review requests or invoice reminders. Open it in a browser, load a customer list (CSV), and it prepares one draft message per customer who is due, applying the owner's rules. The owner approves or skips each draft and sends the approved ones **from their own phone or email**.

## How to try it (2 minutes, made-up data)

1. Open `tool/draft-pack.html` in Chrome, Edge or Firefox (double-click the file; no install, no internet needed).
2. Under **1. Load your list**, choose `tool/SAMPLE-DATA.csv`. Every row in it is made up (fake names, 555-01xx test numbers, `example.com` addresses).
3. Keep the job **Appointment reminder**, type any business name, and set **Today's date** to **2026-12-01** (the sample's dates are around that day).
4. Click **Prepare drafts for review**. You should see 2 drafts and 8 rows that were not drafted, each with its reason: opted out, contacted recently, not due, unclear opt-out value, missing or wrong phone number, unreadable date.
5. Approve a draft: a **Copy** button and an **Open in Messages / email** link appear (only during the sending hours you set).

## What it does

- Reads the CSV only inside the browser tab. The page's security policy blocks every network connection, so nothing is uploaded, and it stores nothing after the tab is closed.
- Rules: always skips customers marked as opted out; skips anyone contacted in the last N days; only offers send links inside the owner's sending hours; stops at a daily limit (at most 200).
- Never guesses: a blank or unclear opt-out value, an unreadable date, a missing or malformed phone number or email, or a blank value for any `{placeholder}` means the row is **not drafted**, and the review screen says why.
- Lets the owner approve, skip or undo each draft. Approved drafts get a copy button and an `sms:` or `mailto:` link that opens the owner's own app with the message filled in; the owner presses send there.
- Keeps an audit log of what happened (file loaded, drafts prepared, every skip reason, approvals, copies, links opened) that the owner can download as CSV.
- Optional stopwatch: times one run of the task and downloads a CSV row with the same columns as `private/pilot-log.csv`. It never estimates time saved.

## What it does not do

- **It never sends anything itself.** No texts, emails, payments or bookings leave the page; the owner sends from their own apps.
- **It does not run Aether programs.** The browser demo of the Aether checker loads Python (Pyodide) from the internet, which this offline page must not do, so the rule checks here are written directly in JavaScript (tested in `tests/test_tool.py`). The matching checked Aether program for a job spec is produced separately by `jobspec/compile.py`.
- It does not connect to a booking app, spreadsheet or phone, and does not read replies.
- It only understands US phone numbers (10 digits, optionally starting with 1).
- It cannot tell whether a message is right for a customer; the owner reads each draft.

The only claim made about the Aether side: programs the checker accepted caused 0 monitor violations on generated test data. Neither this page nor the model is called "safe".
