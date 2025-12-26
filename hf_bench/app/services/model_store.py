from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from huggingface_hub import snapshot_download
from huggingface_hub import HfApi
from fastapi import HTTPException

from app.core.config import Settings
from app.services.hf_policy import repo_size_gb, has_safetensors

@dataclass
class ModelStore:
    settings: Settings
    api: HfApi

    def _local_dir(self, model_id: str, revision: str) -> str:
        safe = model_id.replace("/", "__")
        return os.path.join(self.settings.model_store_dir, safe, revision)

    def ensure_on_nvme(self, model_id: str, revision: str) -> str:
        repo = self.api.repo_info(repo_id=model_id, revision=revision, repo_type="model")
        size_gb = repo_size_gb(repo)

        if size_gb > self.settings.max_repo_size_gb:
            raise HTTPException(
                status_code=413,
                detail=f"Model repo too large ({size_gb:.2f} GB) > limit {self.settings.max_repo_size_gb:.2f} GB",
            )

        if self.settings.allow_safetensors_only and not has_safetensors(repo):
            raise HTTPException(
                status_code=415,
                detail="Model repo has no .safetensors weights (policy ALLOW_SAFETENSORS_ONLY=1).",
            )

        dst = self._local_dir(model_id, revision)
        os.makedirs(dst, exist_ok=True)
        marker = os.path.join(dst, ".READY")
        if os.path.exists(marker):
            return dst

        allow_patterns: List[str] = [
            "*.safetensors",
            "*.json",
            "tokenizer.*",
            "vocab.*",
            "merges.txt",
            "special_tokens_map.json",
            "tokenizer_config.json",
            "generation_config.json",
            "config.json",
            "added_tokens.json",
            "spiece.model",
            "*.model",
        ]
        if not self.settings.allow_safetensors_only:
            allow_patterns.append("*.bin")

        snapshot_download(
            repo_id=model_id,
            revision=revision,
            repo_type="model",
            local_dir=dst,
            local_dir_use_symlinks=False,
            cache_dir=self.settings.hf_cache_dir,
            allow_patterns=allow_patterns,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot", "*.ckpt"],
        )

        with open(marker, "w", encoding="utf-8") as f:
            f.write("ok\n")

        return dst

    def is_on_nvme(self, model_id: str, revision: str) -> bool:
        dst = self._local_dir(model_id, revision)
        marker = os.path.join(dst, ".READY")
        return os.path.exists(marker)
    
    def list_ready_models(self) -> list[dict]:
        """
        Retourne la liste des modèles présents sur disque (READY),
        sous la forme [{model_id, revision, path}]
        """
        out = []

        if not os.path.isdir(self.settings.model_store_dir):
            return out

        for model_dir in os.listdir(self.settings.model_store_dir):
            model_path = os.path.join(self.settings.model_store_dir, model_dir)
            if not os.path.isdir(model_path):
                continue

            # model_dir = model_id avec "/" -> "__"
            model_id = model_dir.replace("__", "/")

            for revision in os.listdir(model_path):
                rev_path = os.path.join(model_path, revision)
                marker = os.path.join(rev_path, ".READY")
                if os.path.isdir(rev_path) and os.path.exists(marker):
                    out.append(
                        {
                            "model_id": model_id,
                            "revision": revision,
                            "path": rev_path,
                        }
                    )

        return out