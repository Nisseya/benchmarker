from domain.ports.repository import RepositoryPort
from domain.models.evaluation import TaskResult, EvaluationSession
from infrastructure.persistence.tables import EvaluationTable, TaskResultTable
from sqlalchemy.orm import Session

class PostgresRepository(RepositoryPort):
    def __init__(self, session: Session):
        self.session = session

    def save_evaluation_session(self, evaluation: EvaluationSession):
        # 1. Map Domaine -> Table SQLAlchemy
        db_eval = EvaluationTable(
            id=evaluation.id,
            team_id=evaluation.team_id,
            session_id=evaluation.session_id,
            language=evaluation.language,
            model_name=evaluation.model_name,
            status=evaluation.status,
            created_at=evaluation.created_at
        )
        self.session.add(db_eval)
        self.session.commit()

    def save_task_result(self, result: TaskResult):
        # 2. Map Domaine -> Table SQLAlchemy
        db_result = TaskResultTable(
            id=result.id,
            evaluation_id=result.evaluation_id,
            question_id=result.question_id,
            generated_code=result.generated_code,
            is_correct=result.is_correct,
            silver_score=result.silver_score,
            generation_duration=result.generation_duration,
            execution_metrics=result.metrics.__dict__ # On sérialise la dataclass en dict pour le JSONB
        )
        self.session.add(db_result)
        self.session.commit()