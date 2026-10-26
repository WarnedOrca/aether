"""One offline 4-bit model load and short generation; process exit frees the GPU."""
import argparse
import logging
import os
import time

from stages.common import ROOT, check_license, model_load_kwargs, use_repo_hf_cache, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    os.environ["HF_HUB_OFFLINE"] = "1"
    use_repo_hf_cache()
    from stages.preflight import gpu_idle
    gpu_idle()
    check_license(args.model, logging.getLogger(__name__))
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    started = time.monotonic()
    kw = model_load_kwargs(args.model)
    tok = AutoTokenizer.from_pretrained(args.model, **kw)
    model = AutoModelForCausalLM.from_pretrained(args.model, **kw, device_map="cuda",
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16))
    model.eval()
    enc = tok("Write a short greeting.", return_tensors="pt").to("cuda")
    with torch.inference_mode():
        generated = model.generate(**enc, min_new_tokens=20, max_new_tokens=20, do_sample=False,
                                   max_time=180, pad_token_id=tok.eos_token_id)
    torch.cuda.synchronize()
    result = {"model": args.model, "tokens": generated.shape[1] - enc["input_ids"].shape[1],
              "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
              "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
              "free_bytes": torch.cuda.mem_get_info()[0], "seconds": time.monotonic() - started}
    write_json(ROOT / "eval/results" / f"setup-load-{args.model.split('/')[-1]}.json", result)
    print(result, flush=True)


if __name__ == "__main__":
    main()
