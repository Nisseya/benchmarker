from sqlalchemy import Column, String, Float, Boolean, ForeignKey, DateTime, Table, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
import uuid
from datetime import datetime

Base = declarative_base()

# Question <-> DataContext
question_data_contexts = Table(
    "question_data_contexts",
    Base.metadata,
    Column("question_id", PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("context_id", PG_UUID(as_uuid=True), ForeignKey("data_contexts.id", ondelete="CASCADE"), primary_key=True),
)

# Team <-> Participants (Membres d'équipe)
team_members = Table(
    "team_members",
    Base.metadata,
    Column("team_id", PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
    Column("participant_id", PG_UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True),
)

# --- TABLES PRINCIPALES ---

class HackathonTable(Base):
    __tablename__ = "hackathon"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class ParticipantTable(Base):
    __tablename__ = "participants"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    last_name = Column(Text, nullable=False)
    first_name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False)

class TeamTable(Base):
    __tablename__ = "teams"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hackathon_id = Column(PG_UUID(as_uuid=True), ForeignKey("hackathon.id", ondelete="CASCADE"))
    name = Column(Text, nullable=False)
    api_key_hash = Column(Text, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    members = relationship("ParticipantTable", secondary=team_members, backref="teams")
    evaluations = relationship("EvaluationTable", backref="team")

class DataContextTable(Base):
    __tablename__ = "data_contexts"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    schema_definition = Column(JSONB)
    storage_link = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class QuestionTable(Base):
    __tablename__ = "questions"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    gold_code = Column(Text, nullable=False)
    language = Column(String, nullable=False)
    category = Column(String)
    difficulty = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    contexts = relationship("DataContextTable", secondary=question_data_contexts)

class EvaluationTable(Base):
    __tablename__ = "evaluations"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"))
    session_id = Column(PG_UUID(as_uuid=True), nullable=False)
    language = Column(String, nullable=False)
    model_name = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    results = relationship("TaskResultTable", backref="evaluation", cascade="all, delete-orphan")

class TaskResultTable(Base):
    __tablename__ = "task_results"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id = Column(PG_UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"))
    question_id = Column(PG_UUID(as_uuid=True), ForeignKey("questions.id"))
    generated_code = Column(Text)
    is_correct = Column(Boolean, default=False)
    silver_score = Column(Float, default=0.0)
    generation_duration = Column(Float)
    execution_metrics = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)