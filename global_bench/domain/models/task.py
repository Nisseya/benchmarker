from typing import Optional, List, Literal
from dataclasses import dataclass, field
from uuid import UUID

@dataclass(frozen=True)
class DataContext:
    id: UUID
    name: str
    schema_definition: dict  # JSON structural information
    storage_link: str
    is_active: bool = True

@dataclass(frozen=True)
class Question:
    id: UUID
    content: str
    gold_code: str
    language: Literal["SQL","Python", "Polars", "Postgres"]
    category: Optional[str]  # join, aggregate, etc.
    difficulty: Literal['easy', 'medium', 'hard', 'extra_hard']
    contexts: List[DataContext] = field(default_factory=list)   