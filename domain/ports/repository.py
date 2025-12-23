from abc import ABC, abstractmethod
from typing import List, Optional
from domain.models.benchmark import BenchmarkTask, BenchmarkResult

class RepositoryPort(ABC):
    @abstractmethod
    def get_task_by_id(self, task_id: str) -> Optional[BenchmarkTask]:
        """Récupère une question et son code 'Gold' de référence."""
        pass

    @abstractmethod
    def save_result(self, result: BenchmarkResult) -> None:
        """Sauvegarde le score, le temps et la consommation de ressources."""
        pass

    @abstractmethod
    def get_all_tasks(self, category: str) -> List[BenchmarkTask]:
        """Récupère une série de tests (ex: tous les SQL de Spider)."""
        pass
    
    @abstractmethod
    def get_team_history(self, team_id: str) -> List[Evaluation]:
        """Récupère tout l'historique d'une équipe pour faire des graphiques de progression."""
        pass

    @abstractmethod
    def get_leaderboard(self, category: str) -> List[Dict]:
        """Calcule le meilleur score de chaque équipe pour le classement général."""
        pass