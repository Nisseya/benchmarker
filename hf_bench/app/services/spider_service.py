from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.core.config import SPIDER_QUESTIONS_TABLE
from app.domain.spider.models import (
    SchemaTextOptions,
    SpiderQuestion,
    SpiderQuestionWithSchema,
)
from app.domain.spider.repository import SpiderRepository


class SpiderService:
    def __init__(
        self,
        *,
        conn,
        schema_options: SchemaTextOptions | None = None,
        questions_table: str = SPIDER_QUESTIONS_TABLE,
    ):
        self.conn = conn
        self.repo = SpiderRepository(conn, questions_table=questions_table)
        self.schema_options = schema_options or SchemaTextOptions(
            use_original_names=True,
            include_types=False,
            max_columns_per_table=60,
            max_total_chars=8000,
        )
        self._schema_cache: Dict[str, str] = {}

    def list_questions(
        self,
        *,
        source_file: Optional[str] = None,
        db_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[SpiderQuestion]:
        return self.repo.list_questions(source_file=source_file, db_id=db_id, limit=limit, offset=offset)

    def get_question(self, *, question_id: int) -> Optional[SpiderQuestion]:
        return self.repo.get_question_by_id(question_id=question_id)

    def get_schema_text(self, *, db_id: str) -> str:
        cached = self._schema_cache.get(db_id)
        if cached is not None:
            return cached

        opt = self.schema_options
        tables = self.repo.get_tables(db_id, use_original=opt.use_original_names)
        if not tables:
            raise ValueError(f"Unknown db_id: {db_id}")

        cols = self.repo.get_columns_by_table(db_id, use_original=opt.use_original_names)
        pks = self.repo.get_primary_keys(db_id, use_original=opt.use_original_names)
        fks = self.repo.get_foreign_keys(db_id, use_original=opt.use_original_names)

        table_name = {t.table_id: t.name for t in tables}

        lines: List[str] = [
            "You are given the following database schema.",
            "",
            f"Database: {db_id}",
            "",
            "Tables:",
        ]

        for t in tables:
            c = cols.get(t.table_id, [])
            shown, omitted = _truncate(c, opt.max_columns_per_table)

            col_txt = (
                ", ".join(f"{n}:{ty}" for n, ty in shown)
                if opt.include_types
                else ", ".join(n for n, _ in shown)
            )
            if omitted:
                col_txt += f", … (+{omitted} more)"
            lines.append(f"- {t.name}({col_txt})")

        lines.append("")
        if fks:
            lines.append("Foreign keys:")
            for fk in fks:
                lines.append(
                    f"- {table_name[fk.from_table_id]}.{fk.from_col} references "
                    f"{table_name[fk.to_table_id]}.{fk.to_col}"
                )
        else:
            lines.append("Foreign keys: (none)")

        lines.append("")
        if any(pks.values()):
            lines.append("Primary keys:")
            for tid, pk_cols in pks.items():
                lines.append(f"- {table_name[tid]}: {', '.join(pk_cols)}")
        else:
            lines.append("Primary keys: (none)")

        text = "\n".join(lines)
        if opt.max_total_chars and len(text) > opt.max_total_chars:
            text = text[: opt.max_total_chars - 1] + "…"

        self._schema_cache[db_id] = text
        return text

    def list_questions_with_schema(
        self,
        *,
        source_file: Optional[str] = None,
        db_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[SpiderQuestionWithSchema]:
        qs = self.list_questions(source_file=source_file, db_id=db_id, limit=limit, offset=offset)
        return [
            SpiderQuestionWithSchema(question=q, schema_text=self.get_schema_text(db_id=q.db_id))
            for q in qs
        ]

    def get_question_with_schema(self, *, question_id: int) -> Optional[SpiderQuestionWithSchema]:
        q = self.get_question(question_id=question_id)
        if q is None:
            return None
        return SpiderQuestionWithSchema(question=q, schema_text=self.get_schema_text(db_id=q.db_id))


def _truncate(cols: List[Tuple[str, str]], max_cols: int | None):
    if max_cols is None or len(cols) <= max_cols:
        return cols, 0
    return cols[:max_cols], len(cols) - max_cols
