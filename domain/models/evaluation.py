from dataclasses import dataclass
from datetime import datetime
from .metrics import ExecutionMetrics

@dataclass
class Evaluation:
    evaluation_id: str
    team_id: str
    session_id: str
    task_id: str
    model_name: str
    generated_code: str
    
    # Résultats de validation
    is_correct: bool      # Gold Standard (Output match)
    silver_score: float   # Silver Standard (State/Variables match)
    judge_feedback: str   # Feedback du LLM-as-a-judge
    
    # Métriques techniques
    metrics: ExecutionMetrics
    
    created_at: datetime = datetime.now()

    def final_score(self) -> float:
        """Logique métier : pondération du score final"""
        # Exemple : 70% exactitude technique, 30% efficacité ressources
        base_score = 1.0 if self.is_correct else (self.silver_score * 0.5)
        return base_score