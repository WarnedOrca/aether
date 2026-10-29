#!/bin/bash
# Waits until the GPU has at least 10,400 MiB free (the stage guard needs 10,240 MiB), then resumes the session 4 chain.
cd <repo>
until [ "$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)" -ge 10400 ]; do
  echo "waiting for GPU memory: $(nvidia-smi --query-gpu=memory.free --format=csv,noheader) free at $(date)"; sleep 60
done
echo "=== GPU free enough at $(date); resuming chain"
bash eval/run_session4_chain.sh
