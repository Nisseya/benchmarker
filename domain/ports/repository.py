from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID
from domain.models.evaluation import EvaluationSession, TaskResult
from domain.models.task import Question, DataContext

class RepositoryPort(ABC):
    # --- Gestion des Questions & Contextes (Datasets) ---
    
    @abstractmethod
    def save_data_context(self, context: DataContext) -> None:
        """Persiste un nouveau contexte de données (SQLite/CSV)."""
        pass

    @abstractmethod
    def get_all_contexts(self) -> List[DataContext]:
        """Récupère tous les contextes de données disponibles."""
        pass

    @abstractmethod
    def delete_context(self, context_id: UUID) -> None:
        """Supprime un contexte de données."""
        pass

    @abstractmethod
    def get_tasks_by_categories(self, categories: List[str]) -> List[Question]:
        """Récupère une liste de questions filtrées par catégories."""
        pass

    @abstractmethod
    def get_task_by_id(self, task_id: UUID) -> Optional[Question]:
        """Récupère une question spécifique avec son code Gold."""
        pass

    # --- Gestion des Sessions d'Évaluation ---

    @abstractmethod
    def save_evaluation_session(self, session: EvaluationSession) -> None:
        """Crée une nouvelle session de benchmark (status: pending/running)."""
        pass

    @abstractmethod
    def update_session_status(self, session_id: UUID, status: str) -> None:
        """Met à jour le statut d'une session (completed, failed, etc.)."""
        pass

    @abstractmethod
    def save_task_result(self, result: TaskResult) -> None:
        """Sauvegarde le résultat individuel d'une question exécutée."""
        pass

    # --- Analytics & Reporting ---

    @abstractmethod
    def get_team_history(self, team_id: UUID) -> List[EvaluationSession]:
        """Récupère l'historique complet d'une équipe avec ses résultats."""
        pass

    @abstractmethod
    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """
        Calcule les scores agrégés pour le classement général.
        Retourne typiquement : [{'team_name': str, 'score_avg': float, ...}]
        """
        pass