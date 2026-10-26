"""Shared helpers for the unattended stage scripts: file logging, crash-safe JSONL checkpoints, licence check."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_LICENSES = ("apache-2.0", "mit")


def use_repo_hf_cache() -> None:
    """Keep model downloads inside the repo (gitignored) unless HF_HOME is already set."""
    os.environ.setdefault("HF_HOME", str(ROOT / ".hf-cache"))


def get_logger(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(path.stem)
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    for h in (logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt)
        log.addHandler(h)
    return log


def write_json(path: Path, obj: object) -> None:
    """Atomic write: a crash never leaves a half-written summary or state file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class JsonlCheckpoint:
    """Append-only record file; every record is flushed to disk, and finished keys are skipped on restart."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[dict] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    self.records.append(json.loads(line))
                except json.JSONDecodeError:  # a line cut off by a crash: ignore it, it will be redone
                    break
        self.done = {r["key"] for r in self.records}
        self._f = path.open("w", encoding="utf-8", newline="\n")
        for r in self.records:  # rewrite without any trailing partial line
            self._f.write(json.dumps(r) + "\n")
        self._f.flush()

    def add(self, rec: dict) -> None:
        self._f.write(json.dumps(rec) + "\n")
        self._f.flush()
        os.fsync(self._f.fileno())
        self.records.append(rec)
        self.done.add(rec["key"])

    def close(self) -> None:
        self._f.close()


def check_license(model_id: str, log: logging.Logger) -> str:
    """Read the licence from the model's Hugging Face page metadata; stop unless it is Apache-2.0 or MIT."""
    from huggingface_hub import model_info

    info = model_info(model_id)
    lic = str((info.card_data or {}).get("license", "unknown")).lower()
    log.info("model %s licence on Hugging Face: %s (revision %s)", model_id, lic, info.sha)
    if lic not in ALLOWED_LICENSES:
        log.error("licence %s is not in %s; stopping (ask the owner)", lic, ALLOWED_LICENSES)
        raise SystemExit(2)
    return lic


def model_revision(model_id: str) -> str:
    from huggingface_hub import model_info

    return model_info(model_id).sha or "unknown"
