from __future__ import annotations

import os
import psutil
import torch
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()

@router.get("/health")
async def health():
    proc = psutil.Process(os.getpid())
    rss_mb = proc.memory_info().rss / (1024 * 1024)

    gpu = None
    if torch.cuda.is_available():
        gpu = {
            "device": torch.cuda.get_device_name(0),
            "allocated_mb": torch.cuda.memory_allocated(0) / (1024 * 1024),
            "reserved_mb": torch.cuda.memory_reserved(0) / (1024 * 1024),
        }

    return {
        "status": "ok",
        "device": settings.device,
        "dtype_default": settings.dtype,
        "rss_mb": rss_mb,
        "gpu": gpu,
        "queue_maxsize": settings.queue_maxsize,
        "model_store_dir": settings.model_store_dir,
        "hf_cache_dir": settings.hf_cache_dir,
        "limits": {
            "max_repo_size_gb": settings.max_repo_size_gb,
            "max_new_tokens": settings.max_new_tokens,
            "max_prompt_chars": settings.max_prompt_chars,
            "require_revision": settings.require_revision,
            "allow_safetensors_only": settings.allow_safetensors_only,
            "trust_remote_code": settings.trust_remote_code,
        },
    }
