from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class ExecutionResult:
    success: bool
    output: Any
    captured_state: Dict
    execution_time_ms: float
    memory_peak_mb: float
    error: Optional[str] = None

class ExecutorPort(ABC):
    @abstractmethod
    def execute(self, code: str, db_id: str, context: Dict[str, Any]) -> ExecutionResult:
        """Exécute du code (sql/python) sur un dataset identifié par db_id."""
        raise NotImplementedError
