from __future__ import annotations

from huggingface_hub.hf_api import ModelInfo

def repo_size_gb(repo: ModelInfo) -> float:
    total = 0
    for s in (getattr(repo, "siblings", None) or []):
        size = getattr(s, "size", None)
        if isinstance(size, int):
            total += size
    return total / (1024 ** 3)

def has_safetensors(repo: ModelInfo) -> bool:
    for s in (getattr(repo, "siblings", None) or []):
        name = getattr(s, "rfilename", "") or ""
        if name.endswith(".safetensors"):
            return True
    return False
