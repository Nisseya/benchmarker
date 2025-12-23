from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from domain.ports.repository import RepositoryPort
from domain.models.evaluation import EvaluationSession, TaskResult, ExecutionMetrics
from domain.models.task import Question, DataContext
from infrastructure.persistence.tables import (
    EvaluationTable, 
    TaskResultTable, 
    QuestionTable,
    DataContextTable,
    TeamTable
    # Supposé exister pour le leaderboard
)

class PostgresRepository(RepositoryPort):
    def __init__(self, session: Session):
        self.session = session

    # --- Gestion des Questions & Contextes ---

    def save_data_context(self, context: DataContext) -> None:
        db_context = DataContextTable(
            id=context.id,
            name=context.name,
            schema_definition=context.schema_definition,
            storage_link=context.storage_link,
            is_active=context.is_active
        )
        self.session.merge(db_context) # merge permet update si existe déjà
        self.session.commit()

    def get_all_contexts(self) -> List[DataContext]:
        db_contexts = self.session.query(DataContextTable).all()
        return [
            DataContext(
                id=c.id, name=c.name, schema_definition=c.schema_definition,
                storage_link=c.storage_link, is_active=c.is_active
            ) for c in db_contexts
        ]

    def delete_context(self, context_id: UUID) -> None:
        self.session.query(DataContextTable).filter_by(id=context_id).delete()
        self.session.commit()

    def get_tasks_by_categories(self, categories: List[str]) -> List[Question]:
        db_questions = self.session.query(QuestionTable).filter(
            QuestionTable.category.in_(categories)
        ).all()
        return [self._map_to_question_domain(q) for q in db_questions]

    def get_task_by_id(self, task_id: UUID) -> Optional[Question]:
        db_q = self.session.query(QuestionTable).filter_by(id=task_id).first()
        return self._map_to_question_domain(db_q) if db_q else None

    # --- Gestion des Sessions d'Évaluation ---

    def save_evaluation_session(self, session: EvaluationSession) -> None:
        db_eval = EvaluationTable(
            id=session.id,
            team_id=session.team_id,
            session_id=session.session_id,
            language=session.language,
            model_name=session.model_name,
            status=session.status,
            created_at=session.created_at
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
            execution_metrics=result.metrics.__dict__
        )
        self.session.add(db_result)
        self.session.commit()

    # --- Analytics & Reporting ---

    def get_team_history(self, team_id: UUID) -> List[EvaluationSession]:
        db_sessions = self.session.query(EvaluationTable).filter_by(team_id=team_id).all()
        # Note: Dans une version réelle, on ferait un join pour charger les results
        return [
            EvaluationSession(
                id=s.id, team_id=s.team_id, session_id=s.session_id,
                language=s.language, model_name=s.model_name, status=s.status,
                created_at=s.created_at
            ) for s in db_sessions
        ]

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Calcule le taux de réussite par équipe."""
        query = (
            self.session.query(
                TeamTable.name.label("team_name"),
                func.count(TaskResultTable.id).label("total_tasks"),
                func.sum(func.cast(TaskResultTable.is_correct, func.Integer)).label("correct_tasks")
            )
            .join(EvaluationTable, EvaluationTable.team_id == TeamTable.id)
            .join(TaskResultTable, TaskResultTable.evaluation_id == EvaluationTable.id)
            .group_by(TeamTable.name)
            .order_by(func.sum(func.cast(TaskResultTable.is_correct, func.Integer)).desc())
        )
        
        results = []
        for row in query.all():
            results.append({
                "team_name": row.team_name,
                "score": (row.correct_tasks / row.total_tasks * 100) if row.total_tasks > 0 else 0
            })
        return results

    # --- Mappers Privés ---

    def _map_to_question_domain(self, db_q: QuestionTable) -> Question:
        return Question(
            id=db_q.id,
            content=db_q.content,
            gold_code=db_q.gold_code,
            language=db_q.language,
            category=db_q.category,
            difficulty=db_q.difficulty
        )