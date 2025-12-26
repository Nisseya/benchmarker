from __future__ import annotations
from abc import ABC, abstractmethod


class WorkerSelectorPort(ABC):
    @abstractmethod
    async def select_worker_url(self) -> str:
        raise NotImplementedError
