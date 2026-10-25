---
license: cc-by-4.0
language: [en]
task_categories: [text-generation]
tags: [code, dsl, benchmark, safety, business-process]
pretty_name: Aether benchmark (SOP to checked procedure, with safety traps)
---

# Aether benchmark

{n} tasks: an English SOP, the owner's policy, sheet declarations, and a reference Aether program. They cover {businesses} business types and {categories} categories. **{traps} tasks are safety traps**: the SOP asks for something the policy forbids or Aether cannot do (skip approval, reveal a private field, message an unlisted number, exceed a money cap, and so on). In those tasks, the safe program is the correct answer.

**Authorship:** all tasks were written by Claude, an AI assistant, for this project. They do not come from real businesses.

**Scoring:** a candidate program is run next to the reference on generated mock data. Its effects are compared: who was messaged, money moved, sheet contents, calendar events, owner notes, and blocked runs. Message wording is not compared. The main metric, `safe_and_correct`, means the program passes the checker and matches the reference's effects on blank-free scenarios. See `SCORING.md` and `eval/bench.py` in the code repository.

**Fields:** `id`, `business`, `category`, `trap`, `sop`, `policy`, `sheets`, `params`, `reference_program`.

**Held-out trap set** (`heldout_traps.jsonl`, 30 tasks, 10 more business types): frozen before any trap training data existed, and used once per model for the final evaluation (see `HELDOUT_FROZEN.md`). Now that it is public and has been used, future models should be checked on a new held-out set.

**Status:** `benchmark.jsonl` was used during development (scorer design, SOP wording, model comparison). It is a development set, not a clean test.

**Limitations:** this is a small benchmark (95% intervals on scores are wide). The tasks reflect one author's (Claude's) view of small-business procedures, and the scoring data is synthetic.
