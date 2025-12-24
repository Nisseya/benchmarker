from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, Integer, cast

from domain.ports.repository import RepositoryPort
from domain.models.evaluation import EvaluationSession, TaskResult
from domain.models.task import Question, DataContext
from domain.models.identity import Team, Participant

from infrastructure.persistence.tables import (
    EvaluationTable,
    TaskResultTable,
    QuestionTable,
    DataContextTable,
    TeamTable,
    ParticipantTable,
    team_members,  # <- Table() d'association
)


class PostgresRepository(RepositoryPort):
    def __init__(self, session: Session):
        self.session = session

    # =========================
    # Questions & Data Contexts
    # =========================

    def save_data_context(self, context: DataContext) -> None:
        db_context = DataContextTable(
            id=context.id,
            name=context.name,
            schema_definition=context.schema_definition,
            storage_link=context.storage_link,
            is_active=context.is_active,
        )
        self.session.merge(db_context)
        self.session.commit()

    def get_all_contexts(self) -> List[DataContext]:
        rows = self.session.query(DataContextTable).all()
        return [
            DataContext(
                id=c.id,
                name=c.name,
                schema_definition=c.schema_definition,
                storage_link=c.storage_link,
                is_active=c.is_active,
            )
            for c in rows
        ]

    def delete_context(self, context_id: UUID) -> None:
        self.session.query(DataContextTable).filter_by(id=context_id).delete()
        self.session.commit()

    def get_tasks_by_categories(self, categories: List[str]) -> List[Question]:
        rows = (
            self.session.query(QuestionTable)
            .filter(QuestionTable.category.in_(categories))
            .all()
        )
        return [self._map_to_question_domain(q) for q in rows]

    def get_task_by_id(self, task_id: UUID) -> Optional[Question]:
        row = self.session.query(QuestionTable).filter_by(id=task_id).first()
        return self._map_to_question_domain(row) if row else None

    # =========================
    # Evaluation Sessions
    # =========================

    def save_evaluation_session(self, session: EvaluationSession) -> None:
        db_eval = EvaluationTable(
            id=session.id,
            team_id=session.team_id,
            session_id=session.session_id,
            language=session.language,
            model_name=session.model_name,
            status=session.status,
            created_at=session.created_at,
        )
        self.session.add(db_eval)
        self.session.commit()

    def update_session_status(self, session_id: UUID, status: str) -> None:
        self.session.query(EvaluationTable).filter_by(id=session_id).update({"status": status})
        self.session.commit()

    def save_task_result(self, result: TaskResult) -> None:
        db_result = TaskResultTable(
            id=result.id,
            evaluation_id=result.evaluation_id,
            question_id=result.question_id,
            generated_code=result.generated_code,
            is_correct=result.is_correct,
            silver_score=result.silver_score,
            generation_duration=result.generation_duration,
            execution_metrics=getattr(result, "execution_metrics", None)
            or (result.metrics.__dict__ if getattr(result, "metrics", None) else None),
        )
        self.session.add(db_result)
        self.session.commit()

    def get_session_by_id(self, session_db_id: UUID) -> Optional[EvaluationSession]:
        s = self.session.query(EvaluationTable).filter_by(id=session_db_id).first()
        if not s:
            return None
        return EvaluationSession(
            id=s.id,
            team_id=s.team_id,
            session_id=s.session_id,
            language=s.language,
            model_name=s.model_name,
            status=s.status,
            created_at=s.created_at,
        )

    def get_session_by_session_id(self, session_id: UUID) -> Optional[EvaluationSession]:
        s = self.session.query(EvaluationTable).filter_by(session_id=session_id).first()
        if not s:
            return None
        return EvaluationSession(
            id=s.id,
            team_id=s.team_id,
            session_id=s.session_id,
            language=s.language,
            model_name=s.model_name,
            status=s.status,
            created_at=s.created_at,
        )

    # =========================
    # Teams
    # =========================

    def save_team(self, team: Team) -> None:
        db_team = TeamTable(
            id=team.id,
            name=team.name,
            hackathon_id=team.hackathon_id,
            created_at=team.created_at,
        )
        self.session.merge(db_team)
        self.session.commit()

        if team.members:
            self.session.execute(team_members.delete().where(team_members.c.team_id == team.id))
            self.session.commit()

            for p in team.members:
                self.session.merge(
                    ParticipantTable(
                        id=p.id,
                        first_name=p.first_name,
                        last_name=p.last_name,
                        email=p.email,
                    )
                )
                self.session.execute(
                    team_members.insert().values(team_id=team.id, participant_id=p.id)
                )

            self.session.commit()

    def get_team_by_id(self, team_id: UUID) -> Optional[Team]:
        t = self.session.query(TeamTable).filter_by(id=team_id).first()
        if not t:
            return None

        return Team(
            id=t.id,
            name=t.name,
            hackathon_id=t.hackathon_id,
            created_at=t.created_at,
            members=self._get_team_members(team_id),
        )

    def delete_team(self, team_id: UUID) -> None:
        self.session.query(TeamTable).filter_by(id=team_id).delete()
        self.session.commit()

    def get_teams_by_hackathon(self, hackathon_id: UUID) -> List[Team]:
        teams = self.session.query(TeamTable).filter_by(hackathon_id=hackathon_id).all()
        return [
            Team(
                id=t.id,
                name=t.name,
                hackathon_id=t.hackathon_id,
                created_at=t.created_at,
                members=self._get_team_members(t.id),
            )
            for t in teams
        ]

    def add_participant_to_team(self, team_id: UUID, participant: Participant) -> None:
        self.session.merge(
            ParticipantTable(
                id=participant.id,
                first_name=participant.first_name,
                last_name=participant.last_name,
                email=participant.email,
            )
        )
        self.session.commit()

        exists = (
            self.session.query(team_members)
            .filter(
                team_members.c.team_id == team_id,
                team_members.c.participant_id == participant.id,
            )
            .first()
        )
        if not exists:
            self.session.execute(
                team_members.insert().values(team_id=team_id, participant_id=participant.id)
            )
            self.session.commit()

    def remove_participant_from_team(self, team_id: UUID, participant_id: UUID) -> None:
        self.session.execute(
            team_members.delete().where(
                (team_members.c.team_id == team_id)
                & (team_members.c.participant_id == participant_id)
            )
        )
        self.session.commit()

    # =========================
    # Participants
    # =========================

    def save_participant(self, participant: Participant) -> None:
        self.session.merge(
            ParticipantTable(
                id=participant.id,
                first_name=participant.first_name,
                last_name=participant.last_name,
                email=participant.email,
            )
        )
        self.session.commit()

    def get_all_participants(self) -> List[Participant]:
        rows = self.session.query(ParticipantTable).all()
        return [
            Participant(
                id=p.id,
                first_name=p.first_name,
                last_name=p.last_name,
                email=p.email,
            )
            for p in rows
        ]

    def get_participant_by_id(self, participant_id: UUID) -> Optional[Participant]:
        p = self.session.query(ParticipantTable).filter_by(id=participant_id).first()
        if not p:
            return None
        return Participant(
            id=p.id,
            first_name=p.first_name,
            last_name=p.last_name,
            email=p.email,
        )

    def delete_participant(self, participant_id: UUID) -> None:
        self.session.query(ParticipantTable).filter_by(id=participant_id).delete()
        self.session.commit()

    def get_participant_by_email(self, email: str) -> Optional[Participant]:
        p = self.session.query(ParticipantTable).filter_by(email=email).first()
        if not p:
            return None
        return Participant(
            id=p.id,
            first_name=p.first_name,
            last_name=p.last_name,
            email=p.email,
        )

    # =========================
    # Analytics & Reporting
    # =========================

    def get_team_history(self, team_id: UUID) -> List[EvaluationSession]:
        rows = self.session.query(EvaluationTable).filter_by(team_id=team_id).all()
        return [
            EvaluationSession(
                id=s.id,
                team_id=s.team_id,
                session_id=s.session_id,
                language=s.language,
                model_name=s.model_name,
                status=s.status,
                created_at=s.created_at,
            )
            for s in rows
        ]

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        q = (
            self.session.query(
                TeamTable.id.label("team_id"),
                TeamTable.name.label("team_name"),
                func.count(TaskResultTable.id).label("total_tasks"),
                func.sum(cast(TaskResultTable.is_correct, Integer)).label("correct_tasks"),
            )
            .join(EvaluationTable, EvaluationTable.team_id == TeamTable.id)
            .join(TaskResultTable, TaskResultTable.evaluation_id == EvaluationTable.id)
            .group_by(TeamTable.id, TeamTable.name)
            .order_by(func.sum(cast(TaskResultTable.is_correct, Integer)).desc())
        )

        out: List[Dict[str, Any]] = []
        for row in q.all():
            total = int(row.total_tasks or 0)
            correct = int(row.correct_tasks or 0)
            score = (correct / total * 100.0) if total > 0 else 0.0
            out.append(
                {
                    "team_id": row.team_id,
                    "team_name": row.team_name,
                    "total_tasks": total,
                    "correct_tasks": correct,
                    "score": score,
                }
            )
        return out

    # =========================
    # Private helpers / mappers
    # =========================

    def _get_team_members(self, team_id: UUID) -> List[Participant]:
        rows = (
            self.session.query(ParticipantTable)
            .join(team_members, team_members.c.participant_id == ParticipantTable.id)
            .filter(team_members.c.team_id == team_id)
            .all()
        )
        return [
            Participant(
                id=p.id,
                first_name=p.first_name,
                last_name=p.last_name,
                email=p.email,
            )
            for p in rows
        ]

    def _map_to_question_domain(self, db_q: QuestionTable) -> Question:
        return Question(
            id=db_q.id,
            content=db_q.content,
            gold_code=db_q.gold_code,
            language=db_q.language,
            category=db_q.category,
            difficulty=db_q.difficulty,
        )
