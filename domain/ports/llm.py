from abc import ABC, abstractmethod
from typing import Any

class LLMProviderPort(ABC):
    @abstractmethod
    def generate_code(self, prompt: str, model_id: str) -> str:
        """Demande au modèle de générer le code (SQL ou Python)."""
        pass

    @abstractmethod
    def judge_answer(self, question: str, code: str, output: Any) -> float:
        """Utilise un LLM fort (ex: GPT-4) pour noter la pertinence (0.0 à 1.0)."""
        pass