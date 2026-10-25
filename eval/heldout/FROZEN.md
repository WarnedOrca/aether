# Held-out trap set: frozen

- File: `traps_heldout.txt` (30 trap tasks, 10 business types new to the project)
- Frozen: 2026-10-25, committed before any trap-style training data existed
- SHA-256: `4c44a3913aae0226ef72ad9e7fff9690624c77fa16e4704269c98979964df667`
- Rules: never used for training, tuning, prompt changes, checkpoint choice, or any design decision. Each model is evaluated on it once, at the end. `tests/test_heldout_frozen.py` fails if the file changes.
- Trap types: 26 tasks use types that the trap training data covers (skip-approval, reveal-private, over-limit, unlisted-recipient, send-on-timeout, unbounded, unsupported charge/payment/channel). 4 tasks use **novel** types that are deliberately absent from all training data (delete-data, raise-limit).
- Authorship: written by Claude (an AI assistant), not by real businesses.
