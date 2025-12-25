from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class ExecutionResult:
    success: bool
    output: Any             # Le résultat final (ex: DataFrame ou Scalaire)
    captured_state: Dict    # Silver Standard : l'état des variables locales
    execution_time_ms: float
    memory_peak_mb: float
    error: Optional[str] = None

class ExecutorPort(ABC):
    @abstractmethod
    def execute(self, code: str, context: Dict[str, Any]) -> ExecutionResult:
        """Exécute le code dans un environnement isolé."""
        pass