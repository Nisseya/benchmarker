from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from uuid import UUID

@dataclass(frozen=True)
class Participant:
    id: UUID
    first_name: str
    last_name: str
    email: str

@dataclass(frozen=True)
class Team:
    id: UUID
    name: str
    hackathon_id: UUID
    created_at: datetime
    members: List[Participant] = field(default_factory=list)