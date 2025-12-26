from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import uuid


class BenchmarkRepositoryPort(ABC):
    @abstractmethod
    def create_run(
        self,
        run_id: uuid.UUID,
        model_id: str,
        revision: str,
        db_id: str,
        params: Dict[str, Any],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def end_run(self, run_id: uuid.UUID, status: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def log_event(self, run_id: uuid.UUID, event_type: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def insert_item(self, run_id: uuid.UUID, item: Dict[str, Any]) -> None:
        raise NotImplementedError
