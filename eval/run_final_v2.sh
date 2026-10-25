#!/usr/bin/env bash
# Post-training run (2026-10-25): verification, dev evals, then every condition ONCE on frozen held-out v2.
# Run from the repo root: bash eval/run_final_v2.sh > eval/results/final-v2-log.txt 2>&1
set -u
M=Qwen/Qwen2.5-Coder-1.5B-Instruct
V2=outputs/ft-coder1.5b-v0.2/epoch2
V3=outputs/ft-coder1.5b-v0.3/epoch2
R=eval/results
run() { echo "=== $(date +%H:%M) $*"; uv run --group ml python -u -m "$@" 2>&1 | grep -viE "warning|redirects|Loading weights"; }

# 0. Clean download-and-run test of the published v0.2 adapter
run release.verify_model

# 1. Dev split only (decisions): constrained decoding with v0.2; v0.3 plain on both dev sets
run eval.constrained --adapter $V2 --label v0.2-dev --tasks-dir eval/benchmark
run eval.baseline --model $M --adapter $V3 --label v0.3 --fewshot 0 --suffix=-dev
run eval.baseline --model $M --adapter $V3 --label v0.3 --fewshot 0 --tasks-dir eval/heldout --suffix=-dev

# 2. Held-out v2, each condition exactly once
run eval.baseline --model $M --tasks-dir eval/heldout2 --suffix=-final2
run eval.baseline --model $M --adapter $V2 --label v0.2 --fewshot 0 --tasks-dir eval/heldout2 --suffix=-final2
run eval.baseline --model $M --adapter $V3 --label v0.3 --fewshot 0 --tasks-dir eval/heldout2 --suffix=-final2
run eval.repair --adapter $V2 --label v0.2-heldout2 --tasks-dir eval/heldout2 \
    --plain $R/baseline-Qwen2.5-Coder-1.5B-Instruct-ft-v0.2-zeroshot-heldout2-$(date +%F)-final2.jsonl
run eval.repair --adapter $V3 --label v0.3-heldout2 --tasks-dir eval/heldout2 \
    --plain $R/baseline-Qwen2.5-Coder-1.5B-Instruct-ft-v0.3-zeroshot-heldout2-$(date +%F)-final2.jsonl
run eval.constrained --adapter $V2 --label v0.2-heldout2 --tasks-dir eval/heldout2
run eval.constrained --adapter $V3 --label v0.3-heldout2 --tasks-dir eval/heldout2
echo "=== $(date +%H:%M) done"

# 3. Report: seven conditions with 95% intervals + the pre-registered primary comparison
D=$(date +%F)
uv run python -m eval.final_v2_report \
  base-fewshot=$R/baseline-Qwen2.5-Coder-1.5B-Instruct-heldout2-$D-final2.jsonl \
  v0.2-plain=$R/baseline-Qwen2.5-Coder-1.5B-Instruct-ft-v0.2-zeroshot-heldout2-$D-final2.jsonl \
  "v0.2-repaired=$R/repair-v0.2-heldout2-heldout2-$D.jsonl#repaired" \
  v0.2-constrained=$R/constrained-v0.2-heldout2-heldout2-$D.jsonl \
  v0.3-plain=$R/baseline-Qwen2.5-Coder-1.5B-Instruct-ft-v0.3-zeroshot-heldout2-$D-final2.jsonl \
  "v0.3-repaired=$R/repair-v0.3-heldout2-heldout2-$D.jsonl#repaired" \
  v0.3-constrained=$R/constrained-v0.3-heldout2-heldout2-$D.jsonl \
  --primary v0.3-repaired v0.2-plain --out $R/final-v2-report-$D.json
echo "=== $(date +%H:%M) report written"
