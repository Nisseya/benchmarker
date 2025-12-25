from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class SchemaTextOptions:
    use_original_names: bool = True
    include_types: bool = False
    max_columns_per_table: Optional[int] = None
    max_total_chars: Optional[int] = None


@dataclass(frozen=True)
class SpiderQuestion:
    id: int
    db_id: str
    question: str
    gold_sql: Optional[str]
    source_file: str
    source_index: int
    meta: dict[str, Any]


@dataclass(frozen=True)
class SpiderQuestionWithSchema:
    question: SpiderQuestion
    schema_text: str
