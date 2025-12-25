from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional, Literal
import asyncio

DType = Literal["float16", "bfloat16", "float32"]

@dataclass
class BenchJob:
    job_id: str
    model_id: str
    revision: str
    schema: str
    question: str
    max_new_tokens: int
    temperature: float
    top_p: float
    do_sample: bool
    dtype: DType
    created_at: float = field(default_factory=time.time)
    events: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=300))

@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    revision: str
    dtype: DType
