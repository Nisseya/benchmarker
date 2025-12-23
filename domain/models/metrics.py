from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ExecutionMetrics:
    execution_time_ms: float
    memory_peak_mb: float
    cpu_usage_percent: float
    tokens_generated: Optional[int] = None
    generation_speed_tps: Optional[float] = None # Tokens par seconde