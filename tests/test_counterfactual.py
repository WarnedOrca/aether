"""Counterfactual seed programs (data/synthetic_cf): each one is valid, its forbidden column is really forbidden and
unused, putting the dropped condition back makes the checker reject it (E401), and nothing overlaps an eval task."""

import json
import re

import pytest

from data.generate_counterfactual import ROOT, eval_index, overlaps, select, variants

CF = ROOT / "data/synthetic_cf/train.jsonl"


def rows():
    if not CF.exists():
        pytest.skip("data/synthetic_cf not generated")
    return [json.loads(l) for l in CF.read_text(encoding="utf-8").splitlines()]


def test_every_counterfactual_verifies_and_forbids_its_column():
    from data.gen.patterns import Sample
    from data.generate import verify
    for r in rows():
        prov = r["provenance"]
        col, sheet = prov["column_not_allowed"], prov["sheet"]
        assert verify(Sample("cf", r["domain"], "", r["policy"], r["program"])) == ""
        allowed = re.search(rf"allow read {sheet}\(([^)]*)\)", r["policy"]).group(1)
        assert col not in [c.strip() for c in allowed.split(",")]
        assert re.search(rf"\b{col}\b", r["sheets"])  # the tempting column is still in the sheet the model sees
        body = [l for l in r["program"].splitlines() if not l.strip().startswith("sheet ")]
        assert not any(re.search(rf"\b{col}\b", re.sub(rf"set {col} =", "", l)) for l in body)
        assert prov["hosted_ai_text"] is False and prov["seed_program"] and r["sop"] == ""


def test_putting_the_dropped_condition_back_is_rejected_with_e401():
    from data.gen.patterns import Sample
    from data.generate import verify
    for r in rows()[:60]:
        cond = r["provenance"]["dropped_condition"]
        restored = re.sub(r"(let \w+ = filter \w+ where )", rf"\g<1>{cond} and ", r["program"], count=1)
        assert "E401" in verify(Sample("cf", r["domain"], "", r["policy"], restored))


def test_no_overlap_with_dev_or_heldout_and_many_columns():
    idx = eval_index()
    rs = rows()
    assert all(overlaps(r["program"], idx) == "" for r in rs)
    cols = {r["provenance"]["column_not_allowed"] for r in rs}
    assert len(cols) >= 10
    assert sum(r["provenance"]["column_not_allowed"] == "status" for r in rs) <= 300


def test_variants_and_selection_on_a_small_example():
    seed = {"program": 'procedure P {\n  about "x"\n  policy Q\n  sheet S "S" { a: Text, b: Text, c: Text }\n  trigger every day at 08:00\n\n'
                       '  let all = fetch S\n  let due = filter all where a == "1" and b == "2"\n}',
            "policy": "policy Q {\n  allow read S(a, b, c)\n}"}
    vs = variants(seed)
    assert {v["column"] for v in vs} == {"a", "b"}
    v = next(v for v in vs if v["column"] == "b")
    assert 'where a == "1"\n' in v["program"] + "\n" and "allow read S(a, c)" in v["policy"]
    cands = [{"column": c, "seed_id": f"s{i}"} for i, c in enumerate(["x"] * 10 + ["y"] * 2)]
    picked = select(cands, 6, 1, max_per_column=3)
    assert sum(p["column"] == "x" for p in picked) == 3 and sum(p["column"] == "y" for p in picked) == 2


def test_merge_keeps_old_rows_and_adds_new_ones_idempotently(tmp_path):
    from stages.merge_cf import merge
    from stages.stage3_paraphrase import build_splits

    def rec(key, accepted=True):
        return {"key": key, "seed_id": key.split("#")[0], "trap": "none", "policy": "p", "sheets": "s", "program": "x",
                "sop": "w", "accepted": accepted, "reject_reason": "", "provenance": {"hosted_ai_text": False}}
    v4, cf, seeds = tmp_path / "v4", tmp_path / "cf", tmp_path / "seeds"
    for d in (v4, cf, seeds):
        d.mkdir()
    old = [rec(f"train-{i}#0") for i in range(30)] + [rec("train-99#0", accepted=False)]
    new = [rec(f"cf-train-{i}-status#0") for i in range(10)]
    (v4 / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in old))
    (cf / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in new))
    (seeds / "train.jsonl").write_text("".join(json.dumps({"id": r["seed_id"], "provenance": {"column_not_allowed": "status"}}) + "\n" for r in new))
    (v4 / "summary.json").write_text("{}")
    info = merge(v4, cf, seeds)
    assert info["new_share"] == round(10 / 40, 4)
    first = {s: (v4 / f"{s}.jsonl").read_text() for s in ("train", "valid")}
    rows = [json.loads(l) for s in first.values() for l in s.splitlines()]
    assert len(rows) == 40
    old_rows = [r for s in build_splits(old).values() for r in s]
    assert all(r in rows for r in old_rows)  # old accepted rows unchanged
    assert all(r["provenance"]["counterfactual"]["column_not_allowed"] == "status" for r in rows if r["id"].startswith("cf-"))
    merge(v4, cf, seeds)
    assert {s: (v4 / f"{s}.jsonl").read_text() for s in ("train", "valid")} == first
