from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.core.config import Settings
from app.domain.models import ModelSpec

def torch_dtype(dtype: str) -> torch.dtype:
    d = dtype.lower()
    if d == "float16":
        return torch.float16
    if d == "bfloat16":
        return torch.bfloat16
    if d == "float32":
        return torch.float32
    raise ValueError(f"Unsupported dtype: {dtype}")

@dataclass
class GpuRuntime:
    settings: Settings
    _key: Optional[Tuple[str, str, str]] = None
    _tokenizer: Any = None
    _model: Any = None

    def unload(self) -> None:
        self._key = None
        self._tokenizer = None
        self._model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def ensure_loaded(self, model_spec: ModelSpec, local_path: str) -> None:
        key = (model_spec.model_id, model_spec.revision, model_spec.dtype)
        if self._key == key and self._model is not None and self._tokenizer is not None:
            return

        self.unload()

        dt = torch_dtype(model_spec.dtype)
        tok = AutoTokenizer.from_pretrained(local_path, trust_remote_code=self.settings.trust_remote_code, use_fast=True)
        mdl = AutoModelForCausalLM.from_pretrained(
            local_path,
            trust_remote_code=self.settings.trust_remote_code,
            torch_dtype=dt if self.settings.device.startswith("cuda") else None,
            device_map=None,
        )
        mdl.eval()
        mdl.to(self.settings.device)

        self._key = key
        self._tokenizer = tok
        self._model = mdl

    def gpu_stats(self) -> Optional[Dict[str, float]]:
        if not torch.cuda.is_available():
            return None
        return {
            "allocated_mb": torch.cuda.memory_allocated(0) / (1024 * 1024),
            "reserved_mb": torch.cuda.memory_reserved(0) / (1024 * 1024),
        }

    @property
    def tokenizer(self):
        return self._tokenizer

    @property
    def model(self):
        return self._model
