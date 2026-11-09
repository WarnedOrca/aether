# Onboarding a business owner: first session, check-ins, and helpers

This is the step-by-step for one pilot with one owner and one task (appointment reminders, follow-ups, review requests or invoice reminders). It goes with `interview-guide.md` (the first conversation), `pilot-agreement-template.md` (signed before anything else), and `MEASURING-IMPACT.md` (what to record and the rules for using it). It contains no example numbers.

**Three rules hold throughout.**
1. The customer list stays on the owner's computer. You never receive, copy, photograph or look through it.
2. The owner reviews and approves every message and sends it from their own phone or email. The tool never sends anything.
3. Every number you write down comes from the owner's timing, the page's downloads, or the owner's own words, and is marked as which.

## Before the first session (you, at home)

- [ ] The pilot agreement is filled in, a parent or guardian has read it, and the owner has a copy to read first.
- [ ] From the first conversation you know the one task and the owner's words for it.
- [ ] **Optional AI setup, done on your own computer** (the owner never needs a GPU or any install). Turn the owner's description of the job (only the job, never customer details) into a settings file and three message wordings:
  ```
  .venv/Scripts/python.exe -m jobspec.make_settings "<the owner's description of the job>" --out settings.json
  .venv/Scripts/python.exe -m jobspec.writer --business-type "<type>" --tone friendly --job <job> --out templates.json
  ```
  The first command says whether the local AI model or the keyword rules produced the settings, and refuses jobs the tool must not do. If either command fails, skip it: the owner can fill in the form by hand.
- [ ] Put `tool/draft-pack.html`, `tool/SAMPLE-DATA.csv` and (optional) `settings.json` and `templates.json` on a USB stick or in an email to the owner. They are small files.

## What the owner brings

- Their computer, with Chrome, Edge or Firefox.
- An export of their customer list as a CSV file (from their booking app or spreadsheet). They do the export themselves. If they don't know how, show them where the export button usually is in their app, but let them click it.
- About 45 minutes, on a normal working day, ideally at the time they usually do this task.

## The first session (about 45 minutes)

1. **Agreement (5 min).** Go through it together; everyone signs. Tick the box about naming the business **only** if the owner says yes; the default is no.
2. **Time the old way first (10-15 min).** Before showing the tool, the owner does one batch of the task the way they always do, and you time it with the page's stopwatch (bottom of the page; phase `before`) or a phone stopwatch. Don't help and don't comment. Write the minutes in `private/pilot-log.csv` as a `before` row with `how_measured` = "stopwatch in the draft pack tool" or "owner timed it", and `check_in_baseline_week4_week8_other` = `baseline`. If it's not possible to time it today, record the owner's own estimate instead and **mark it as an estimate**. The report never uses estimates for time saved.
3. **Try the sample file (5 min).** On the owner's computer, open `draft-pack.html` and load `SAMPLE-DATA.csv` (made-up people), so they see what it does without their data.
4. **Set up their job (5 min).** Either press **Import settings file** and **Import message suggestions**, or fill in the form by hand. The page shows every suggested setting and wording and changes nothing until the owner presses Use. Then go through each field with them: job, text or email, days since last contact, sending hours, daily limit, the wording. The owner decides; edits are expected.
5. **Run it on their real list (10 min).** The owner loads their own CSV. You look away from the screen while the file is loaded and the drafts are shown; ask them to read out only the counts ("12 drafts, 5 not drafted"). They check the "Not drafted, and why" list and fix their sheet if something is wrong (an unclear opt-out, an unreadable date). They approve or skip each draft, send each approved one from their own app, and press **Mark sent** after each one they actually sent.
6. **Time the new way (same session or next batch).** Time one whole batch with the tool: from opening the page to the last message sent, phase `after`. A batch done during this first session includes learning the page, so also time the next normal batch at week 1 if possible.
7. **Set up revenue tracking (5 min).** Ask how they would know whether reminders brought customers back, and record their choice in `revenue_tracking_method`:
   - `reply_to_rebook`: customers reply to the reminder to rebook, and the owner counts those replies;
   - `rebooking_link_or_code`: a booking link or code used only in these messages (the owner adds it in the message box; the wording checks block links only in AI suggestions, never the owner's own edits);
   - `before_after_comparison`: the same weeks compared before and after, from their own records;
   - `none` is a fine answer.
   Also ask "Roughly what is one appointment or sale worth to you?" and record their figure as owner-stated. Never suggest one.
8. **Downloads (2 min).** The owner presses **Download audit log** (and the stopwatch download if used) and gives you those files. They contain row numbers, counts, reason codes, settings and timings, never customer names, numbers or message text. Open them together first so the owner can see that. Save them in `private/pilot-logs/<business code>/`.
9. **Close.** Agree on the week-4 and week-8 check-in dates, and on how the owner sends you the audit log downloads in between (email is fine; they are not customer data).

## Between sessions

- The owner uses the page on their own whenever they do the task, and downloads the audit log each time (or at least weekly).
- You save each download into `private/pilot-logs/<code>/` and run the report:
  ```
  .venv/Scripts/python.exe scripts/pilot_report.py --pilot-log private/pilot-log.csv --logs private/pilot-logs
  ```
- If the owner reports a problem (a wrong draft, a confusing reason), write it in `notes` with the date and fix it before the next check-in.

## Week-4 check-in (about 20 minutes)

1. Time one normal batch with the tool (phase `after`), the same task and size as the baseline if possible.
2. Ask, in the same words as at baseline: no-shows per week, rebookings per week (`*_owner_reported`), and how much of a hassle the task is (1-5).
3. Ask "Would you recommend this to another business owner?" (yes/no) and whether they introduced you to anyone (count real introductions only).
4. If they track revenue: "Over the last four weeks, how much revenue do you think came from the reminders, and how did you count it?" Write their figure with its period. Then ask them to confirm it in writing (a short email or text: "I confirm about $X over [period] came from rebooked reminders, counted by [method]"). Save the confirmation in `private/` and set `revenue_confirmed_in_writing_yes_no_and_date`. Without written confirmation the figure is recorded but **may not be used anywhere**.
5. Run the report together and show them their own numbers.
6. Ask whether they want to continue to week 8. If the agreement said 4 weeks, extending needs their yes in writing.

## Week-8 check-in

Same as week 4, with `check_in` = `week8`. Ask again about naming the business; record the answer and date. Ask whether they want to keep the tool. The page is theirs to keep either way.

## For classmates who help with outreach

You can help a lot without ever seeing customer data.

**You may:**
- Help find businesses on the agreed target list (only ones you or your family already know, after a parent or guardian has seen the list).
- Practise conversations using `practice-conversations.md`, and come along to a first conversation if the owner agrees.
- Time a batch with the stopwatch, write down the owner's own answers, and type rows into the pilot log on the project computer.
- Run `scripts/pilot_report.py` and check that every number it prints matches a file.

**You may not:**
- Look at, receive, copy, photograph or forward an owner's customer list, a draft message, or anything on the review screen. When the owner loads their list, look away.
- Write down any customer name, phone number, email or detail, even "just for a moment".
- Suggest numbers to an owner ("so about 2 hours saved?"), round numbers up, or fill in a blank cell.
- Collect sentences, examples or data from friends or family to test or train anything.
- Post, share or present any pilot result. Only the project owner does that, following `MEASURING-IMPACT.md`.

If you see customer data by accident, tell the project owner the same day; don't keep or repeat it.
