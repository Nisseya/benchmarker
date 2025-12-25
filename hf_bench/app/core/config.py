from __future__ import annotations

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    hf_cache_dir: str = os.getenv("HF_HOME", "/models")
    model_store_dir: str = os.getenv("MODEL_STORE_DIR", "/models_store")

    require_revision: bool = os.getenv("REQUIRE_REVISION", "1") == "1"
    allow_safetensors_only: bool = os.getenv("ALLOW_SAFETENSORS_ONLY", "1") == "1"
    trust_remote_code: bool = False

    max_repo_size_gb: float = float(os.getenv("MAX_REPO_SIZE_GB", "30"))
    max_new_tokens: int = int(os.getenv("MAX_NEW_TOKENS", "512"))
    max_prompt_chars: int = int(os.getenv("MAX_PROMPT_CHARS", "20000"))
    queue_maxsize: int = int(os.getenv("QUEUE_MAXSIZE", "100"))

    device: str = os.getenv("HF_DEVICE", "cuda")
    dtype: str = os.getenv("HF_DTYPE", "float16")

settings = Settings()
