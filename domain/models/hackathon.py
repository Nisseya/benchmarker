from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

@dataclass(frozen=True)
class Hackathon:
    id: UUID
    name: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    created_at: datetime
