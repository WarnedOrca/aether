"""The held-out trap set must never change after freezing (eval/heldout/FROZEN.md)."""

import hashlib
from pathlib import Path

FROZEN_SHA256 = "4c44a3913aae0226ef72ad9e7fff9690624c77fa16e4704269c98979964df667"


def test_heldout_file_unchanged():
    data = Path("eval/heldout/traps_heldout.txt").read_bytes()
    assert hashlib.sha256(data).hexdigest() == FROZEN_SHA256


HELDOUT2_SHA256 = {"tasks_a.txt": "ae4bc88d620ad63748e7668fb2e4283a4ce94684a10b98899ae10e651230de29", "tasks_b.txt": "ef0e87464a11da86b79049b5f06cea91e96d2578fdbafb3f4c591caeacbd63b3"}


def test_heldout2_files_unchanged():
    for name, digest in HELDOUT2_SHA256.items():
        data = Path("eval/heldout2", name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name


HELDOUT3_SHA256 = {"tasks_a.txt": "e8225dc8281abb2c83dbd79ca3b8a0e130060002ac23587c3fa8fdeb780ebdca", "tasks_b.txt": "2c8e219ff8cd20fedbc43d023abe0ae6440297e82b7c7519dddc4c0b02b2b59d", "tasks_c.txt": "ad1be20b4298206e5cbd454a75c62a866e2220f5863bd8a5f5684d199d7979a0"}


def test_heldout3_files_unchanged():
    for name, digest in HELDOUT3_SHA256.items():
        data = Path("eval/heldout3", name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
