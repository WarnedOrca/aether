#!/bin/bash
# Session 4 chain (dev split only; no stage 5, no held-out). Every step is skipped if its result exists, resumes if it
# was interrupted, and commits its result locally. Rerun this script after a shutdown: `bash eval/run_session4_chain.sh`.
# With --wait it first waits for an already running stage 3 wrapper instead of starting stage 3 itself.
cd "$(dirname "$0")/.."
export HF_HOME="$PWD/.hf-cache" HF_HUB_OFFLINE=1
PY=.venv/Scripts/python.exe
R=eval/results
commit() { git add "$@" && git commit -q -m "$MSG

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && echo "=== committed: $MSG"; }
stop() { echo "=== STOP: $1 ($(date))"; exit 1; }

# 1. stage 3 wordings for the counterfactual programs
if [ ! -f data/synthetic_v4_cf/summary.json ]; then
  if [ "$1" = "--wait" ]; then until grep -q "=== done" logs/stage3-cf.wrapper.log 2>/dev/null; do sleep 60; done
  else bash eval/run_stage3_cf.sh > logs/stage3-cf.wrapper.log 2>&1; fi
fi
[ -f data/synthetic_v4_cf/summary.json ] || stop "stage 3 did not finish"
echo "=== stage 3 done $(date)"

# 2. quality gate on the new wordings, merge into data/synthetic_v4, commit
if ! git log --oneline -20 | grep -q "merge counterfactual wordings (session 4)"; then
  $PY -m stages.quality_gate data/synthetic_v4_cf --sources data/synthetic_cf --out $R/stage3-quality-gate-cf-session4.json > logs/gate-cf.out 2>&1
  $PY -m stages.merge_cf > logs/merge-cf.out 2>&1 || stop "merge"
  MSG="data: merge counterfactual wordings (session 4)" commit data/synthetic_v4 data/synthetic_v4_cf $R/stage3-quality-gate-cf-session4.json
fi

# 3. stage 4, same recipe, new output folder (checkpoints every 25 steps; a rerun resumes)
if [ ! -f outputs/qlora-7b-v3/summary.json ]; then
  for try in 1 2 3 4; do
    echo "=== stage4 try $try $(date)"
    $PY -u -m stages.stage4_qlora --model Qwen/Qwen2.5-Coder-7B-Instruct --data data/synthetic_v4 --out outputs/qlora-7b-v3 \
      >> logs/stage4-v3.out 2>> logs/stage4-v3.err
    [ $? -eq 0 ] && break; sleep 30
  done
fi
[ -f outputs/qlora-7b-v3/summary.json ] || stop "stage 4 did not finish"
mkdir -p $R/ft && cp outputs/qlora-7b-v3/summary.json $R/ft/qlora-7b-v3-summary.json && cp outputs/qlora-7b-v3/train_log.jsonl $R/ft/qlora-7b-v3-train_log.jsonl
if ! git ls-files --error-unmatch $R/ft/qlora-7b-v3-summary.json >/dev/null 2>&1 || ! git diff --quiet -- $R/ft/qlora-7b-v3-summary.json; then
  MSG="feat: stage 4 on data with counterfactual rows (qlora-7b-v3), logs" commit $R/ft/qlora-7b-v3-summary.json $R/ft/qlora-7b-v3-train_log.jsonl
fi

# 4. plain dev evaluation of each epoch (resumable)
export AETHER_LOAD_4BIT=1
for ep in epoch1 epoch2; do
  out=$R/baseline-q7b-v3-$ep-dev-benchmark
  if [ ! -f $out.json ]; then
    for try in 1 2 3; do
      $PY -u -m stages.gpu eval.baseline --model Qwen/Qwen2.5-Coder-7B-Instruct --adapter outputs/qlora-7b-v3/$ep --label q7b-v3-$ep \
        --fewshot 0 --tasks-dir eval/benchmark --batch 2 --out $out >> logs/dev-eval-v3-$ep.out 2>> logs/dev-eval-v3-$ep.err
      [ $? -eq 0 ] && break; sleep 20
    done
    [ -f $out.json ] || stop "plain eval $ep"
    MSG="feat: dev evaluation of q7b-v3 $ep (plain)" commit $out.json $out.jsonl $out.config.json
  fi
done

# 5. checker feedback on the epoch with more plain correct (tie: epoch 2, as in session 3)
best=$($PY -c "
import json;c={e:json.load(open(f'$R/baseline-q7b-v3-{e}-dev-benchmark.json'))['benchmark']['safe_and_correct'] for e in ('epoch1','epoch2')}
print('epoch1' if c['epoch1']>c['epoch2'] else 'epoch2')")
echo "=== feedback run on $best"
out=$R/repair-q7b-v3-$best-dev-benchmark
if [ ! -f $out.json ]; then
  for try in 1 2 3; do
    $PY -u -m stages.gpu eval.repair --model Qwen/Qwen2.5-Coder-7B-Instruct --adapter outputs/qlora-7b-v3/$best \
      --plain $R/baseline-q7b-v3-$best-dev-benchmark.jsonl --tasks-dir eval/benchmark --label q7b-v3-$best-dev --rounds 3 \
      --out $out >> logs/repair-v3.out 2>> logs/repair-v3.err
    [ $? -eq 0 ] && break; sleep 20
  done
  [ -f $out.json ] || stop "feedback run"
  MSG="feat: exploratory dev checker-feedback run for q7b-v3 $best" commit $out.json $out.jsonl $out.config.json
fi

# 6. reports (CPU)
V02=$R/baseline-Qwen2.5-Coder-1.5B-Instruct-ft-v0.2-zeroshot-2026-10-25-final-rescored.jsonl
V2E2=$R/baseline-Qwen2.5-Coder-7B-Instruct-ft-q7b-v2-epoch2-zeroshot-benchmark-2026-10-28-dev.jsonl
$PY -m eval.dev_report --reference $V02 --train data/synthetic_v4 --run q7b-v2-epoch2=$V2E2 \
  --run q7b-v3-epoch1=$R/baseline-q7b-v3-epoch1-dev-benchmark.jsonl --run q7b-v3-epoch2=$R/baseline-q7b-v3-epoch2-dev-benchmark.jsonl \
  --out $R/dev-report-q7b-v3-session4.json > logs/report-v3.out 2>&1 || stop "dev report"
$PY -m eval.dev_failure_analysis --run v0.2=$V02 --run q7b-v2-epoch2=$V2E2 \
  --run q7b-v3-epoch1=$R/baseline-q7b-v3-epoch1-dev-benchmark.jsonl --run q7b-v3-epoch2=$R/baseline-q7b-v3-epoch2-dev-benchmark.jsonl \
  --out $R/dev-failure-diagnosis-session4.json >> logs/report-v3.out 2>&1 || stop "failure analysis"
$PY -m eval.dev_repair_compare --a q7b-v3-$best=$out.jsonl --b v0.2=$R/repair-v0.2-dev-rerun-benchmark.jsonl \
  --out $R/dev-repair-compare-session4.json >> logs/report-v3.out 2>&1 || stop "feedback compare"
MSG="feat: session 4 dev reports (q7b-v3 vs v0.2)" commit $R/dev-report-q7b-v3-session4.json $R/dev-failure-diagnosis-session4.json $R/dev-repair-compare-session4.json
echo "=== chain finished $(date)"
