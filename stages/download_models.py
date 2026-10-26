"""Download owner-locked snapshots, anonymously, with bounded HTTP waits.

Reject all non-huggingface.co requests, including redirected weight hosts.
If Hub storage needs another domain, the owner must run the command themselves.
"""
import os
from urllib.parse import urlparse

from stages.common import locked_model, use_repo_hf_cache
from stages.preflight import MODELS


def main():
    use_repo_hf_cache()
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["HF_HUB_ETAG_TIMEOUT"] = "30"
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "60"
    try:
        import httpx
    except ModuleNotFoundError:
        import httpx2 as httpx  # installed Hub version uses this renamed HTTP client
    from huggingface_hub import set_client_factory, snapshot_download

    def restrict(request):
        if urlparse(str(request.url)).hostname != "huggingface.co":
            raise RuntimeError(f"Network permission limited to huggingface.co; blocked host {request.url.host}")

    set_client_factory(lambda: httpx.Client(timeout=60, follow_redirects=True, event_hooks={"request": [restrict]}))
    failed = False
    for model in MODELS:
        revision = locked_model(model)["revision"]
        try:
            path = snapshot_download(model, revision=revision, token=False, max_workers=2,
                                     allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "*.tiktoken"])
            print(f"Downloaded {model}: {path}", flush=True)
        except Exception as exc:
            failed = True
            # Exception messages may contain signed redirect URLs; only print the type.
            detail = str(exc) if type(exc) is RuntimeError and str(exc).startswith("Network permission limited") else type(exc).__name__
            print(f"FAILED {model}: {detail}; see HANDOFF.md for owner download command", flush=True)
    raise SystemExit(int(failed))


if __name__ == "__main__":
    main()
