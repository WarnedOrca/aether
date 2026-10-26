"""Read-only readiness checks. No model downloads and no GPU allocation."""
import argparse
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from stages.common import ROOT, locked_model, use_repo_hf_cache, write_json

MODELS = ("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-Coder-7B-Instruct")


def snapshot(model):
    from huggingface_hub import snapshot_download
    entry = locked_model(model)
    path = Path(snapshot_download(model, revision=entry["revision"], local_files_only=True))
    if not path.name.startswith(entry["revision"]):
        raise ValueError(f"Revision mismatch: {path.name}")
    required = ["config.json", "tokenizer_config.json", "tokenizer.json", "model.safetensors.index.json"]
    index = json.loads((path / required[-1]).read_text())
    required += sorted(set(index["weight_map"].values()))
    for name in required:
        if not (path / name).is_file() or (path / name).stat().st_size == 0:
            raise ValueError(f"Missing/empty snapshot file: {name}")
    return str(path)


def smi(*args):
    return subprocess.check_output(["nvidia-smi", *args], text=True, timeout=20).strip()


def gpu_free():
    free = [int(x) for x in smi("--query-gpu=memory.free", "--format=csv,noheader,nounits").splitlines()]
    if not free or free[0] < 10 * 1024:
        raise ValueError(f"GPU 0 needs at least 10 GiB free; MiB free: {free}")
    return {"free_mib": free}


def gpu_idle():
    jobs = smi("--query-compute-apps=pid,process_name", "--format=csv,noheader")
    if jobs:
        raise ValueError(f"Compute processes already running: {jobs}")
    return "No compute processes"


def disk():
    free = shutil.disk_usage(ROOT).free
    # Room for both downloads, checkpoint rotation, and intermediate outputs.
    if free < 50 * 1024**3:
        raise ValueError(f"Need 50 GiB free; bytes free: {free}")
    return {"free_bytes": free, "minimum_gib": 50}


def bnb():
    module = importlib.import_module("bitsandbytes")
    # Import can succeed even when its native library failed to load.
    from bitsandbytes.cextension import lib
    if not getattr(lib, "compiled_with_cuda", False):
        raise RuntimeError("bitsandbytes native CUDA library did not load")
    return module.__version__


def frozen():
    subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_heldout_frozen.py"],
                   cwd=ROOT, check=True, timeout=120, capture_output=True, text=True)
    return "Frozen hash tests passed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="eval/results/setup-preflight.json")
    args = ap.parse_args()
    use_repo_hf_cache()
    checks = [("lock file", lambda: {m: locked_model(m) for m in MODELS})]
    checks += [(m, lambda m=m: snapshot(m)) for m in MODELS]
    checks += [("bitsandbytes", bnb), ("GPU memory", gpu_free), ("disk space", disk),
               ("held-out frozen hashes", frozen), ("no other GPU job", gpu_idle)]
    results = []
    for name, fn in checks:
        try:
            detail, passed = fn(), True
        except Exception as exc:
            detail, passed = str(exc), False
        print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}", flush=True)
        results.append({"check": name, "passed": passed, "detail": detail})
    write_json(ROOT / args.out, {"checks": results, "passed": all(r["passed"] for r in results)})
    raise SystemExit(0 if all(r["passed"] for r in results) else 1)


if __name__ == "__main__":
    main()
