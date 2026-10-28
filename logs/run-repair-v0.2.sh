#!/bin/bash
# Exploratory dev-only checker-feedback run for v0.2 (1.5B base + LoRA). Resumable: rerun this script; finished tasks are skipped.
# Not offline: the 1.5B base has no owner-reviewed models.lock.json entry, so it loads from the default HF cache as on 2026-10-25.
cd <repo>
unset HF_HUB_OFFLINE AETHER_LOAD_4BIT
export HF_HOME="$HOME/.cache/huggingface" HF_HUB_DISABLE_IMPLICIT_TOKEN=1
for try in 1 2 3; do
  .venv/Scripts/python.exe -u -m stages.gpu eval.repair --model Qwen/Qwen2.5-Coder-1.5B-Instruct --adapter outputs/ft-coder1.5b-v0.2/epoch2 \
    --plain eval/results/baseline-Qwen2.5-Coder-1.5B-Instruct-ft-v0.2-zeroshot-2026-10-25-final-rescored.jsonl \
    --tasks-dir eval/benchmark --label v0.2-dev-rerun --rounds 3 --out eval/results/repair-v0.2-dev-rerun-benchmark \
    >> logs/repair-v0.2.out 2>> logs/repair-v0.2.err
  rc=$?; echo "=== try $try exit $rc at $(date)"; [ $rc -eq 0 ] && break; sleep 20
done
echo "=== done $(date)"
