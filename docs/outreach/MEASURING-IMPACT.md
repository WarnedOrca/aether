# Measuring impact

The question a pilot has to answer is simple: **did one real task get easier for one real person, and by how much?** This page says what to write down, how, and where it may be used. It deliberately contains no example numbers, so nothing here can be mistaken for a result.

## Where the records live

Two files in `private/`, which is listed in `.gitignore`, so they are never committed or pushed:

- `private/target-list.csv`: businesses you might contact (name, type, how you'd reach them, status, date, notes). Only businesses you or your family already know, and only after a parent or guardian has seen the list.
- `private/pilot-log.csv`: one row per measurement. Use a short code for the business in this file (for example its initials), so the measurements and the names are not in the same row.

Never put customer names, phone numbers, emails or any customer details in either file.

## The measures, in plain words

Each row records one measurement for one task, either **before** the pilot or **after** (during) it.

| Column | What it means | How to get it honestly |
|---|---|---|
| `date` | The day you wrote it down | Today's date, not the day it happened |
| `business_code` | Which business (initials or a code) | Same code every time for the same business |
| `task` | The one task, in a few words | Use the same wording each time |
| `phase_before_or_after` | `before` = how it worked before the pilot; `after` = while using the tool | One phase per row |
| `minutes_per_task` | How long one round of the task takes the owner or staff | Best: the owner times it on a normal day. Acceptable: the owner's own estimate, marked as an estimate in `how_measured` |
| `tasks_per_week` | How many times a week it happens | Count from their records if they have them; otherwise their estimate |
| `messages_late_or_missed_per_week` | Customer messages that went out late or not at all because of this task | Only if the owner can actually tell; leave blank rather than guess |
| `owner_rating_1_to_5` | The owner's answer to "How much of a hassle is this task?" (1 = none, 5 = a lot) | Ask the same question, the same way, before and after |
| `how_measured` | Exactly how the numbers were obtained | For example "owner's estimate in interview", "owner timed it", "counted from booking app" |
| `owner_ok_to_mention_business_yes_no_and_date` | Whether the owner said the business may be named, and when | Written permission only (the pilot agreement has a box for this) |
| `notes` | Anything that affects how to read the row | For example "holiday week", "new staff member" |
| `check_in_baseline_week4_week8_other` | Which check-in the row belongs to | `baseline` at the first session, then `week4` and `week8` (see `ONBOARDING.md`) |
| `no_shows_per_week_owner_reported` | No-shows in a normal week, as the owner tells it | Ask the same way each time; from their booking records if they have them, otherwise their estimate (say which in `how_measured`) |
| `rebookings_per_week_owner_reported` | Missed or cancelled appointments that were rebooked in a normal week | Same as above |
| `would_recommend_yes_no` | "Would you recommend this to another business owner?" | Ask at week 4 and week 8; write their answer, not yours |
| `referrals_given_count` | How many other owners they actually introduced you to | Count real introductions only |
| `revenue_tracking_method` | How the owner will tell whether reminders brought money back | One of `reply_to_rebook` (customers reply to the reminder to rebook), `rebooking_link_or_code` (a link or code only used in these messages), `before_after_comparison` (same weeks compared before and after), or `none` |
| `value_of_one_appointment_or_sale_owner_stated_usd` | What one appointment or sale is worth, in dollars, as the owner states it | The owner's own figure; never yours |
| `owner_reported_revenue_usd` and `owner_reported_revenue_period` | The revenue the owner says came from the reminders, and over what period | Only what the owner says, with the period ("4 weeks") |
| `revenue_confirmed_in_writing_yes_no_and_date` | Whether the owner confirmed that revenue statement in writing (email, text or signed note), and when | `yes 2026-..-..` only when you have the written confirmation saved in `private/` |

## Where the page's downloads go, and the report

Save the owner's downloads from the draft pack page (the audit log and the stopwatch file) into `private/pilot-logs/<business code>/`, one folder per business. They contain row numbers, counts, reason codes and settings, never customer names, phone numbers or message text. Then run:

```
.venv/Scripts/python.exe scripts/pilot_report.py --pilot-log private/pilot-log.csv --logs private/pilot-logs
```

It prints, per business and in total: messages drafted, approved and marked sent by the owner; rows skipped by reason; timed minutes per batch before and after, and the percent change; hours saved per month; how often AI suggestions were kept, edited or rejected; owner-reported no-shows and rebookings; and owner-reported revenue, printed separately. It also prints how many businesses have at least 4 weeks of data. Anything missing prints as "no data". Try it on the made-up files first: `--pilot-log scripts/sample/pilot-log.csv --logs scripts/sample/pilot-logs`.

## Definitions (use these words only in these meanings)

- **Efficiency** means the percent drop in the owner's **timed** minutes for the **same job** (one batch of the same task), before versus after: (after - before) / before. It is computed only from timed runs: the page's stopwatch, or the owner timing it themselves. An estimate is never compared with a timing.
- **Hours saved per month** = (mean timed minutes before - mean timed minutes after) x the owner's stated batches per week x 52 / 12 / 60. It is only computed when there is at least one timed run before and one after.
- **Sent** means the owner pressed "Mark sent" after sending from their own app. The page never sends anything and cannot see whether a message went out.
- **Revenue** is never measured by the tool. A revenue figure may be written anywhere (application, paper, README, website, conversation) **only if all three hold**: it is owner-reported (a row in `private/pilot-log.csv`); the owner confirmed it in writing (`revenue_confirmed_in_writing...` starts with `yes` and the confirmation is saved); and it is phrased as "owners report ..." with the period, never as a measured result. `scripts/pilot_report.py` counts only confirmed figures as usable.

Time saved per week is worked out later from the before and after rows (minutes per task × tasks per week, before minus after). Do this only when both rows exist and were measured the same way. An estimate compared with a timed measurement is not a fair comparison; write down which is which.

## Things that make a number untrustworthy

- It was estimated by you instead of the owner.
- The before and after were measured differently, or in very different weeks.
- It comes from a dry run on made-up data. Dry runs show what the tool *would* do; they don't measure anything about the business.
- It was rounded up, "about", or remembered later.

When in doubt, leave the cell blank and add a note. A blank is honest; a guess is not.

## The rule for using results

**Nothing goes into a Common App entry, the research paper, the README or any public page unless:**

1. it is a row in `private/pilot-log.csv`, with a date and a `how_measured` that someone else could check, and
2. if the business would be named or identifiable, the owner gave written permission to mention it (the `owner_ok_to_mention…` column says yes, with a date).

If a business didn't give permission, it can still be counted without a name ("one local business"), but only if the number itself is in the log. Results from this activity stay in this activity: don't reuse the same numbers in another activity's entry or count one pilot twice. Before using any number, also record it in the vault's `CLAIMS.md` and `METRICS.md` with the date and where it came from.

Until there are real rows in the log, the honest description of this phase is what was done (conversations held, tasks understood, dry runs shown), not what changed.
