#!/bin/bash
# Session 4 step 2: local Qwen2.5-7B wordings for the counterfactual seed programs. Resumable: rerun; finished wordings are skipped.
cd "$(dirname "$0")/.."
export HF_HOME="$PWD/.hf-cache" HF_HUB_OFFLINE=1
for try in 1 2 3 4; do
  .venv/Scripts/python.exe -u -m stages.stage3_paraphrase --sources data/synthetic_cf --per-program 3 --load-4bit \
    --shuffle-seed 11 --out data/synthetic_v4_cf >> logs/stage3-cf.out 2>> logs/stage3-cf.err
  rc=$?; echo "=== stage3-cf try $try exit $rc at $(date)"; [ $rc -eq 0 ] && break; sleep 30
done
echo "=== done $(date)"
