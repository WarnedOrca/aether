"""The held-out trap set must never change after freezing (eval/heldout/FROZEN.md)."""

import hashlib
from pathlib import Path

FROZEN_SHA256 = "4c44a3913aae0226ef72ad9e7fff9690624c77fa16e4704269c98979964df667"


def test_heldout_file_unchanged():
    data = Path("eval/heldout/traps_heldout.txt").read_bytes()
    assert hashlib.sha256(data).hexdigest() == FROZEN_SHA256
