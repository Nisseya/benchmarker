from sqlalchemy import Column, String, Float, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship
import uuid

Base = declarative_base()

class EvaluationTable(Base):
    __tablename__ = "evaluations"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(PG_UUID(as_uuid=True), ForeignKey("teams.id"))
    session_id = Column(PG_UUID(as_uuid=True), nullable=False)
    language = Column(String)
    model_name = Column(String)
    status = Column(String)
    created_at = Column(DateTime)

class TaskResultTable(Base):
    __tablename__ = "task_results"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = Column(PG_UUID(as_uuid=True), ForeignKey("evaluations.id"))
    question_id = Column(PG_UUID(as_uuid=True), ForeignKey("questions.id"))
    generated_code = Column(String)
    is_correct = Column(Boolean)
    silver_score = Column(Float)
    generation_duration = Column(Float)
    execution_metrics = Column(JSON)