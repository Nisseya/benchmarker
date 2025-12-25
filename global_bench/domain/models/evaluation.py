from typing import Optional, List
from dataclasses import dataclass, field
from uuid import UUID
from datetime import datetime

@dataclass(frozen=True)
class ExecutionMetrics:
    cpu_usage_percent: float
    ram_usage_mb: float
    duration_ms: float
    error_msg: Optional[str] = None

@dataclass
class TaskResult:
    id: UUID
    evaluation_id: UUID
    question_id: UUID
    generated_code: str
    is_correct: bool
    silver_score: float
    generation_duration: float
    metrics: ExecutionMetrics
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class EvaluationSession:
    id: UUID
    team_id: UUID
    session_id: UUID         # ID unique pour le run complet
    language: str
    model_name: str
    status: str              # 'pending', 'running', 'completed', 'failed'
    results: List[TaskResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)