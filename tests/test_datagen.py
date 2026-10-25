import json
import random
from pathlib import Path

from data.generate import PATTERNS, verify
from data.gen.domains import DOMAINS, TEST_DOMAINS


def test_every_pattern_produces_verified_samples():
    rng = random.Random(7)
    made = 0
    for d in DOMAINS[:6]:
        for name, fn in PATTERNS.items():
            for batch in (False, True):
                s = fn(d, rng, batch)
                if s is None:
                    continue
                assert verify(s) == "", (name, d.name, verify(s))
                made += 1
    assert made > 40


def test_generation_is_deterministic():
    a = PATTERNS["reminder"](DOMAINS[0], random.Random(3), False)
    b = PATTERNS["reminder"](DOMAINS[0], random.Random(3), False)
    assert a == b


def test_test_split_only_holds_out_domains():
    path = Path("data/synthetic/test.jsonl")
    if not path.exists():
        return
    domains = {json.loads(line)["domain"] for line in path.open(encoding="utf-8")}
    assert domains <= TEST_DOMAINS
    train = {json.loads(line)["domain"] for line in Path("data/synthetic/train.jsonl").open(encoding="utf-8")}
    assert not (train & TEST_DOMAINS)
