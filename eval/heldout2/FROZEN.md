# Held-out set v2: frozen

- Files: `tasks_a.txt` (48 tasks), `tasks_b.txt` (42 tasks); 90 tasks = 30 traps + 60 general, 15 business types used nowhere in training data or earlier sets.
- Drafted by Claude (an AI assistant), not by real businesses.
- Frozen: 2026-10-25, committed BEFORE any new training, tuning, repair-loop or decoding experiments (v0.3 work).
- SHA-256 tasks_a.txt: `ae4bc88d620ad63748e7668fb2e4283a4ce94684a10b98899ae10e651230de29`
- SHA-256 tasks_b.txt: `ef0e87464a11da86b79049b5f06cea91e96d2578fdbafb3f4c591caeacbd63b3`
- Rules: never used for training, tuning, prompt changes, checkpoint choice, or any decision. Each condition is evaluated once, at the end. All decisions use the dev split (the 110-task benchmark + held-out v1, both "used during development"). `tests/test_heldout_frozen.py` fails if these files change.
- Validation: every reference program parses, passes the checker, scores itself perfectly, and no task can be passed by a do-nothing program (`uv run python -m eval.validate_tasks eval/heldout2`).
- Overlap (`overlap_report.json`; `overlap_report_without_blank_sentence.json` excludes the templated blank-cell sentence): vs all training data (synthetic 2,166 + trap 450 SOPs) max whole-SOP Jaccard 0.25, 0 shared word 8-grams, 7 tasks with a sentence ratio >= 0.75 (short generic phrases such as "I approve each one."). vs the 110-task benchmark (an evaluation set, never trained on): max Jaccard 0.46, up to 6 shared 8-grams in one task (similar refund wording). vs held-out v1: max Jaccard 0.26, 0 shared 8-grams.
