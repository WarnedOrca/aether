# Held-out set v3: frozen

- Files: `tasks_a.txt`, `tasks_b.txt`, `tasks_c.txt` (24 tasks each); 72 tasks = 36 non-trap + 36 traps (12 trap kinds), 31 categories, 18 business types used nowhere in training data or earlier evaluation sets.
- **Drafted by Claude (an AI assistant)**, not by real businesses. Phrasing deliberately varied (casual notes, lowercase, terse, long) and not produced by the training-data generator. Evaluation only: never training data.
- Frozen: 2026-10-25, committed BEFORE any new training data generation or training (stages 3-5).
- SHA-256 tasks_a.txt: `e8225dc8281abb2c83dbd79ca3b8a0e130060002ac23587c3fa8fdeb780ebdca`
- SHA-256 tasks_b.txt: `2c8e219ff8cd20fedbc43d023abe0ae6440297e82b7c7519dddc4c0b02b2b59d`
- SHA-256 tasks_c.txt: `ad1be20b4298206e5cbd454a75c62a866e2220f5863bd8a5f5684d199d7979a0`
- Rules: never used for training, tuning, prompt changes, checkpoint choice, or any decision. Each final condition is evaluated once, at the end (stage 5). All decisions use the dev split (110-task benchmark, held-out v1, held-out v2: all now "used"). `tests/test_heldout_frozen.py` fails if these files change.
- Validation: every reference program parses, passes the checker, scores itself perfectly, and no task can be passed by a do-nothing program (`python -m eval.validate_tasks eval/heldout3`). Two reference fixes and one weak-task fix were made before freezing (batch preview bound, daily order cap, a missing read column; a filter that a do-nothing program could pass).
- Overlap (`overlap_report.json`, `python -m eval.overlap_check eval/heldout3`): vs all training data (synthetic 2,166, trap 450, v3 1,320 SOPs) max whole-SOP char-5-gram Jaccard 0.21, 0 shared word 8-grams, 1 task with a sentence ratio >= 0.75 (a short generic phrase). vs earlier evaluation sets (never trained on): max Jaccard 0.31, up to 2 shared 8-grams; exact repeats are short approval phrases only ("I approve each text.", "Ask me before each refund.").
- Primary metrics are declared in the vault decision log (2026-10-25) and in `HANDOFF.md`: non-trap success, trap safe-alternative rate (reported separately), and unsafe programs reaching execution.
