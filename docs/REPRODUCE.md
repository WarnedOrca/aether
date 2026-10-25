# Reproducing every number

Requirements: [uv](https://docs.astral.sh/uv/). The model steps need an NVIDIA GPU with 12 GB of memory (they also work on a free Kaggle or Colab GPU). Everything costs $0 and uses only open-weight models.

```bash
uv sync                                        # checker, interpreter, tests
uv run pytest                                  # 288 tests
uv run python eval/run_properties.py --seeds 100
uv run python -m data.generate --per-combo 8   # regenerates data/synthetic (seed 0, deterministic)
uv run python -m eval.check_benchmark          # 110/110 references valid
uv run python -m eval.weak_tasks               # 0 tasks passable by a do-nothing program

uv sync --group ml                             # torch (CUDA 12.8), transformers, accelerate, peft
uv run --group ml python -m eval.baseline --model Qwen/Qwen2.5-Coder-1.5B-Instruct --suffix=-v2
uv run --group ml python -m eval.baseline --model Qwen/Qwen2.5-Coder-1.5B-Instruct --fewshot 0 --suffix=-v2
uv run --group ml python -m eval.baseline --model Qwen/Qwen3-1.7B --suffix=-v2
uv run --group ml python -m eval.baseline --model Qwen/Qwen2.5-Coder-0.5B-Instruct --suffix=-v2
uv run --group ml python -m eval.baseline --model HuggingFaceTB/SmolLM2-1.7B-Instruct --batch 2 --suffix=-v2
uv run --group ml python -m training.finetune --out outputs/ft-coder1.5b      # about 71 min on an RTX 4070
uv run --group ml python -m eval.baseline --model Qwen/Qwen2.5-Coder-1.5B-Instruct --adapter outputs/ft-coder1.5b/epoch2 --fewshot 0 --suffix=-v2
uv run python -m eval.compare eval/results/baseline-Qwen2.5-Coder-1.5B-Instruct-ft-zeroshot-*-v2.jsonl eval/results/baseline-Qwen2.5-Coder-1.5B-Instruct-2026-*-v2.jsonl

# v0.2 (released model) and the frozen held-out trap set
uv run python -m data.generate_traps --n 450 --seed 1                        # trap samples + overlap report
uv run --group ml python -m training.finetune --with-traps --out outputs/ft-coder1.5b-v0.2
M=Qwen/Qwen2.5-Coder-1.5B-Instruct
uv run --group ml python -m eval.baseline --model $M --tasks-dir eval/heldout --suffix=-final
uv run --group ml python -m eval.baseline --model $M --adapter outputs/ft-coder1.5b/epoch2 --label v0.1 --fewshot 0 --tasks-dir eval/heldout --suffix=-final
uv run --group ml python -m eval.baseline --model $M --adapter outputs/ft-coder1.5b-v0.2/epoch2 --label v0.2 --fewshot 0 --tasks-dir eval/heldout --suffix=-final
uv run --group ml python -m eval.baseline --model $M --adapter outputs/ft-coder1.5b-v0.2/epoch2 --label v0.2 --fewshot 0 --suffix=-final

uv run python -m release.build                 # dist/: dataset, benchmark (+ held-out), v0.2 model card (+ adapter), Space
uv run --group demo python demo/app.py         # local demo at http://127.0.0.1:7860
```

Greedy decoding makes generation deterministic for a fixed batch size and GPU. Small numeric differences across GPUs can change a few outputs.
