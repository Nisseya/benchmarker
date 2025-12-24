from abc import ABC, abstractmethod
from typing import Any

class LLMProviderPort(ABC):
    @abstractmethod
    async def generate_code(self, prompt: str, model_id: str) -> str:
        """Demande au modèle de générer le code (SQL ou Python)."""
        pass

    @abstractmethod
    async def judge_answer(self, question: str, code: str, output: Any, model_name: str) -> float:
        """Retourne une note 0.0 -> 1.0"""
        ...