#!/bin/bash
# Session 5: the ONE-TIME held-out v3 evaluation (stage 5) of v0.2. Rerun this exact script only to resume after a
# crash or shutdown: finished conditions are never run again and an interrupted one continues only its unfinished
# tasks (same command, same conditions file). Never edit stages/stage5_conditions.json.
cd <repo>
export HF_HOME="$HOME/.cache/huggingface" HF_HUB_OFFLINE=1
echo "=== stage 5 start $(date)"
.venv/Scripts/python.exe -u -m stages.stage5_eval --conditions stages/stage5_conditions.json >> logs/stage5.out 2>> logs/stage5.err
echo "=== stage 5 exit $? at $(date)"
