"""Assemble release folders (Hugging Face-ready) into dist/ from tracked sources.

Usage: uv run python -m release.build
Creates (dist/ is gitignored):
  dist/dataset/    synthetic train/valid/test JSONL + dataset card
  dist/benchmark/  benchmark.jsonl (110 tasks) + card
  dist/model/      model card (+ the LoRA adapter, if outputs/ft-coder1.5b/epoch2 exists)
Every number in the cards is read from committed result files, never typed by hand.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from eval.bench import load_tasks

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
RES = ROOT / "eval" / "results"
ADAPTER = ROOT / "outputs" / "ft-coder1.5b-v0.2" / "epoch2"  # v0.2 is the released model


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_dataset() -> None:
    out = DIST / "dataset"
    out.mkdir(parents=True, exist_ok=True)
    for split in ("train", "valid", "test"):
        shutil.copy(ROOT / "data/synthetic" / f"{split}.jsonl", out / f"{split}.jsonl")
    for split in ("train", "valid"):
        shutil.copy(ROOT / "data/synthetic_traps" / f"{split}.jsonl", out / f"traps_{split}.jsonl")
    shutil.copy(ROOT / "data/synthetic_traps/overlap_report.json", out / "traps_overlap_report.json")
    stats = _json(ROOT / "data/synthetic/stats.json")
    card = (ROOT / "release/templates/dataset_card.md").read_text(encoding="utf-8")
    card = card.format(train=stats["splits"]["train"], valid=stats["splits"]["valid"], test=stats["splits"]["test"],
                       kept=stats["kept"], patterns=len(stats["patterns"]), test_domains=", ".join(stats["test_domains"]))
    (out / "README.md").write_text(card, encoding="utf-8")


def build_benchmark() -> None:
    out = DIST / "benchmark"
    out.mkdir(parents=True, exist_ok=True)
    tasks = load_tasks()
    with open(out / "benchmark.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for t in tasks:
            f.write(json.dumps({"id": t.id, "business": t.business, "category": t.category, "trap": t.trap,
                                "sop": t.sop, "policy": t.policy, "sheets": t.sheets, "params": t.params,
                                "reference_program": t.program}) + "\n")
    card = (ROOT / "release/templates/benchmark_card.md").read_text(encoding="utf-8")
    card = card.format(n=len(tasks), traps=sum(t.trap != "none" for t in tasks),
                       businesses=len({t.business for t in tasks}), categories=len({t.category for t in tasks}))
    (out / "README.md").write_text(card, encoding="utf-8")
    shutil.copy(ROOT / "eval/benchmark/README.md", out / "SCORING.md")
    held = load_tasks(ROOT / "eval/heldout")
    with open(out / "heldout_traps.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for t in held:
            f.write(json.dumps({"id": t.id, "business": t.business, "category": t.category, "trap": t.trap,
                                "sop": t.sop, "policy": t.policy, "sheets": t.sheets, "params": t.params,
                                "reference_program": t.program}) + "\n")
    shutil.copy(ROOT / "eval/heldout/FROZEN.md", out / "HELDOUT_FROZEN.md")


def build_model() -> None:
    out = DIST / "model"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    H = RES / "ft"
    h21, h2b, h1b = _json(H / "heldout-v0.2-vs-v0.1.json"), _json(H / "heldout-v0.2-vs-base.json"), _json(H / "heldout-v0.1-vs-base.json")
    dev = _json(H / "dev-v0.2-vs-v0.1.json")
    dev_base = _json(RES / "baseline-Qwen2.5-Coder-1.5B-Instruct-2026-10-25-v2.json")
    run = _json(H / "ft-coder1.5b-v0.2-run.json")
    traps = _json(ROOT / "data/synthetic_traps/overlap_report.json")
    v2 = _json(RES / "final-v2-report-2026-10-25.json")
    v2b = _json(H / "heldout2-v0.2-vs-base.json")
    names = {"base-fewshot": "Base model + reference card + 3 examples", "v0.2-plain": "**v0.2 plain (this adapter)**",
             "v0.2-repaired": "v0.2 with checker feedback", "v0.2-constrained": "v0.2 grammar-constrained",
             "v0.3-plain": "v0.3 plain (not released)", "v0.3-repaired": "v0.3 with checker feedback (not released)",
             "v0.3-constrained": "v0.3 grammar-constrained (not released)"}
    v2_rows = "\n".join(f"| {names[k]} | {c['correct']} | {c['ci95'][0]:.2f}-{c['ci95'][1]:.2f} | {c['traps_correct']} |"
                        for k, c in v2["conditions"].items())
    pa, pb = v2["primary"]["a"], v2["primary"]["b"]
    card = (ROOT / "release/templates/model_card.md").read_text(encoding="utf-8")
    card = card.format(
        v2_rows=v2_rows, v2_pa=v2["conditions"][pa]["correct"], v2_pb=v2["conditions"][pb]["correct"],
        v2_pp=f"{v2['primary']['mcnemar_exact_p']:.2g}", v2_v2=v2b["a_correct"], v2_base=v2b["b_correct"],
        v2_p_base=f"{v2b['mcnemar_exact_p']:.2g}",
        h_base=h2b["b_correct"], h_base_lo=h2b["b_ci95"][0], h_base_hi=h2b["b_ci95"][1],
        h_v1=h21["b_correct"], h_v1_lo=h21["b_ci95"][0], h_v1_hi=h21["b_ci95"][1],
        h_v2=h21["a_correct"], h_v2_lo=h21["a_ci95"][0], h_v2_hi=h21["a_ci95"][1],
        p_v2_v1=f"{h21['mcnemar_exact_p']:.2g}", p_v2_base=f"{h2b['mcnemar_exact_p']:.2g}",
        n_traps=traps["train"], d_base=round(dev_base["benchmark"]["safe_and_correct"] * 110),
        d_v1=dev["b_correct"], d_v1_traps=dev["b_traps_correct"], d_v2=dev["a_correct"], d_v2_traps=dev["a_traps_correct"],
        p_dev=f"{dev['mcnemar_exact_p']:.2g}", rank=run["rank"], lr=run["lr"], epochs=run["epochs"],
        n_train=run["train_examples"], n_base=run["train_examples"] - traps["train"],
        minutes=round(run["seconds"] / 60), gpu=run["gpu"])
    assert h1b["a_correct"] == h21["b_correct"]  # v0.1 counts agree across comparison files
    (out / "README.md").write_text(card, encoding="utf-8")
    if ADAPTER.exists():
        for f in ADAPTER.iterdir():
            if f.name != "README.md":  # peft writes a placeholder card; ours is the real one
                shutil.copy(f, out / f.name)


SPACE_README = """---
title: Aether
emoji: 🧾
colorFrom: indigo
colorTo: gray
sdk: gradio
app_file: app.py
license: apache-2.0
---

Check, explain, and run Aether business procedures in a sandbox. Everything uses mock data; nothing is sent anywhere.
The model tab needs a GPU and is disabled on the free CPU Space.
"""


def build_space() -> None:
    """Hugging Face Space (free CPU) as flat files only (the web uploader cannot create folders).

    The checker and interpreter are installed from the public GitHub repository, whose URL is
    given in the environment variable AETHER_GITHUB_REPO (e.g. https://github.com/<user>/aether.git).
    """
    out = DIST / "space"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    repo = os.environ.get("AETHER_GITHUB_REPO", "")
    shutil.copy(ROOT / "demo/app.py", out / "app.py")
    shutil.copy(ROOT / "LICENSE", out / "LICENSE")
    shutil.copy(ROOT / "data/examples/AppointmentReminders.ae", out / "example.ae")
    pkg = f"aether @ git+{repo}" if repo else "# set AETHER_GITHUB_REPO and rebuild: aether @ git+https://github.com/<user>/aether.git"
    (out / "requirements.txt").write_text(f"{pkg}\nlark>=1.2\ngradio>=5\n", encoding="utf-8")
    (out / "README.md").write_text(SPACE_README, encoding="utf-8")
    if not repo:
        print("WARNING: AETHER_GITHUB_REPO not set; dist/space/requirements.txt is incomplete")


if __name__ == "__main__":
    build_dataset()
    build_benchmark()
    build_model()
    build_space()
    print("built:", ", ".join(sorted(str(p.relative_to(ROOT)) for p in DIST.rglob("*") if p.is_file())))
