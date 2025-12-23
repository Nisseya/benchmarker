from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    category: str           # "sql" ou "python"
    question: str
    context_db_path: str    # Path vers la DB SQLite pour Spider
    gold_answer_code: str   # La solution parfaite

@dataclass
class Evaluation:
    evaluation_id: str
    team_id: str
    session_id: str         # ID du run actuel
    task_id: str
    is_correct: bool        # Gold Standard
    silver_score: float     # Silver Standard (variables)
    execution_time_ms: float
    memory_peak_mb: float
    created_at: datetime = datetime.now()