#!/bin/bash
# Exploratory dev-only checker-feedback run for q7b-v2 epoch 2. Resumable: rerun this script; finished tasks are skipped.
cd <repo>
export HF_HOME="$PWD/.hf-cache" HF_HUB_OFFLINE=1 AETHER_LOAD_4BIT=1
for try in 1 2 3; do
  .venv/Scripts/python.exe -u -m stages.gpu eval.repair --model Qwen/Qwen2.5-Coder-7B-Instruct --adapter outputs/qlora-7b-v2/epoch2 \
    --plain eval/results/baseline-Qwen2.5-Coder-7B-Instruct-ft-q7b-v2-epoch2-zeroshot-benchmark-2026-10-28-dev.jsonl \
    --tasks-dir eval/benchmark --label q7b-v2-epoch2-dev --rounds 3 --out eval/results/repair-q7b-v2-epoch2-dev-benchmark \
    >> logs/repair-q7b-v2-epoch2.out 2>> logs/repair-q7b-v2-epoch2.err
  rc=$?; echo "=== try $try exit $rc at $(date)"; [ $rc -eq 0 ] && break; sleep 20
done
echo "=== done $(date)"
