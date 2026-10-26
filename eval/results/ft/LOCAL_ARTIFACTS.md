# Local-only artifacts (not in git, not on Hugging Face unless noted)

Recorded 2026-10-25. Adapters are gitignored (`*.safetensors`); only v0.2 epoch 2 is published (Hugging Face sidchalamala/aether-coder-1.5b-lora). Back these up yourself if you need them.

| Path | What | SHA-256 (adapter_model.safetensors) | Published |
|---|---|---|---|
| `outputs/ft-coder1.5b/epoch1` | v0.1 epoch 1 | `25ebc3a70b889746a68100a4b1317798cd052f385d290748c674f4b36684625a` | no |
| `outputs/ft-coder1.5b/epoch2` | v0.1 epoch 2 | `9e5b2b07a5c169bf082ea960a35e394df583cad162697d1ed06ebbbbc32451cb` | no |
| `outputs/ft-coder1.5b-v0.2/epoch1` | v0.2 epoch 1 | `5eb97d75571d8c401df77f620973f850f684159ea7d2596e173d307f3a8406b2` | no |
| `outputs/ft-coder1.5b-v0.2/epoch2` | v0.2 epoch 2 (released) | `e3dd973d3d19d99629fe235d87a2101940c4ac8b75bbd28050c857f5c1323dc3` | yes |
| `outputs/ft-coder1.5b-v0.3/epoch1` | v0.3 epoch 1 | `d78edc4e850a8af13861b150e3a47975b0f467cb886b45bf39fdd5739ed17f15` | no |
| `outputs/ft-coder1.5b-v0.3/epoch2` | v0.3 epoch 2 (unreleased negative result) | `94b5865a5ef1cb19fe329954d3804983dca25825b87e9d9a95eb1fdca67e2d17` | no |
| `outputs/ft-smoke/epoch1` | smoke test | `81f76326864b9c6aa607c0853a355046acba243783a55a694780e5932258a3d2` | no |

Training logs are copied into `eval/results/ft/logs/`.
