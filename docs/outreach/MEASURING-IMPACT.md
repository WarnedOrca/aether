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
