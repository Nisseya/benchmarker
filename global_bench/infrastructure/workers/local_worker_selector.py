from __future__ import annotations
from dataclasses import dataclass

from domain.ports.worker_selector import WorkerSelectorPort


@dataclass(frozen=True)
class LocalWorkerSelector(WorkerSelectorPort):
    url: str = "http://localhost:8001"

    async def select_worker_url(self) -> str:
        return self.url.rstrip("/")
