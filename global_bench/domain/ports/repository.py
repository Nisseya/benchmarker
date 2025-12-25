from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID

from domain.models.evaluation import EvaluationSession, TaskResult
from domain.models.task import Question, DataContext
from domain.models.identity import Team, Participant
from domain.models.hackathon import Hackathon

class RepositoryPort(ABC):
    # =========================
    # Questions & Data Contexts
    # =========================

    @abstractmethod
    def save_data_context(self, context: DataContext) -> None:
        pass

    @abstractmethod
    def get_all_contexts(self) -> List[DataContext]:
        pass

    @abstractmethod
    def delete_context(self, context_id: UUID) -> None:
        pass

    @abstractmethod
    def get_tasks_by_categories(self, categories: List[str]) -> List[Question]:
        pass

    @abstractmethod
    def get_task_by_id(self, task_id: UUID) -> Optional[Question]:
        pass

    # =========================
    # Evaluation Sessions
    # =========================

    @abstractmethod
    def save_evaluation_session(self, session: EvaluationSession) -> None:
        pass

    @abstractmethod
    def update_session_status(self, session_id: UUID, status: str) -> None:
        pass

    @abstractmethod
    def save_task_result(self, result: TaskResult) -> None:
        pass

    @abstractmethod
    def get_session_by_id(self, session_db_id: UUID) -> Optional[EvaluationSession]:
        pass

    @abstractmethod
    def get_session_by_session_id(self, session_id: UUID) -> Optional[EvaluationSession]:
        """
        session_id = l'UUID "public" utilisé côté websocket / UI
        (différent de l'id DB si tu en as deux).
        """
        pass

    # =========================
    # Teams
    # =========================

    @abstractmethod
    def save_team(self, team: Team) -> None:
        pass

    @abstractmethod
    def get_team_by_id(self, team_id: UUID) -> Optional[Team]:
        pass

    @abstractmethod
    def delete_team(self, team_id: UUID) -> None:
        pass

    @abstractmethod
    def get_teams_by_hackathon(self, hackathon_id: UUID) -> List[Team]:
        pass

    @abstractmethod
    def add_participant_to_team(self, team_id: UUID, participant_id: UUID) -> None:
        pass

    @abstractmethod
    def remove_participant_from_team(self, team_id: UUID, participant_id: UUID) -> None:
        pass

    # =========================
    # Participants
    # =========================

    @abstractmethod
    def save_participant(self, participant: Participant) -> None:
        pass

    @abstractmethod
    def get_all_participants(self) -> List[Participant]:
        pass

    @abstractmethod
    def get_participant_by_id(self, participant_id: UUID) -> Optional[Participant]:
        pass

    @abstractmethod
    def delete_participant(self, participant_id: UUID) -> None:
        pass

    @abstractmethod
    def get_participant_by_email(self, email: str) -> Optional[Participant]:
        pass
    
    # =========================
    # Hackathons
    # =========================

    @abstractmethod
    def create_hackathon(self, hackathon: Hackathon) -> None:
        pass

    @abstractmethod
    def get_hackathon_by_id(self, hackathon_id: UUID) -> Optional[Hackathon]:
        pass

    @abstractmethod
    def get_hackathon_by_name(self, name: str) -> Optional[Hackathon]:
        pass

    @abstractmethod
    def list_hackathons(self) -> List[Hackathon]:
        pass

    @abstractmethod
    def delete_hackathon(self, hackathon_id: UUID) -> None:
        pass

    # =========================
    # Analytics & Reporting
    # =========================

    @abstractmethod
    def get_team_history(self, team_id: UUID) -> List[EvaluationSession]:
        pass

    @abstractmethod
    def get_leaderboard(self) -> List[Dict[str, Any]]:
        pass
