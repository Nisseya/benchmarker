from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.domain.spider.models import SpiderQuestion


@dataclass(frozen=True)
class TableRow:
    table_id: int
    name: str


@dataclass(frozen=True)
class ForeignKeyRow:
    from_table_id: int
    from_col: str
    to_table_id: int
    to_col: str


class SpiderRepository:
    def __init__(self, conn, *, questions_table: str):
        self.conn = conn
        self.questions_table = questions_table

    def list_questions(
        self,
        *,
        source_file: Optional[str] = None,
        db_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[SpiderQuestion]:
        where = []
        params: list[Any] = []

        if source_file is not None:
            where.append("source_file = ?")
            params.append(source_file)
        if db_id is not None:
            where.append("db_id = ?")
            params.append(db_id)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        sql = f"""
        SELECT
          id, db_id, question, query,
          source_file, source_index,
          sql_json, query_toks, query_toks_no_value, question_toks
        FROM {self.questions_table}
        {where_sql}
        ORDER BY source_index ASC
        LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = self.conn.execute(sql, params).fetchall()

        out: List[SpiderQuestion] = []
        for r in rows:
            meta = {
                "sql_json": _loads_json(r["sql_json"]),
                "query_toks": _loads_json(r["query_toks"]),
                "query_toks_no_value": _loads_json(r["query_toks_no_value"]),
                "question_toks": _loads_json(r["question_toks"]),
            }
            out.append(
                SpiderQuestion(
                    id=int(r["id"]),
                    db_id=str(r["db_id"]),
                    question=str(r["question"]),
                    gold_sql=str(r["query"]) if r["query"] is not None else None,
                    source_file=str(r["source_file"]),
                    source_index=int(r["source_index"]),
                    meta=meta,
                )
            )
        return out

    def get_question_by_id(self, *, question_id: int) -> Optional[SpiderQuestion]:
        sql = f"""
        SELECT
          id, db_id, question, query,
          source_file, source_index,
          sql_json, query_toks, query_toks_no_value, question_toks
        FROM {self.questions_table}
        WHERE id = ?
        """
        r = self.conn.execute(sql, (question_id,)).fetchone()
        if r is None:
            return None

        meta = {
            "sql_json": _loads_json(r["sql_json"]),
            "query_toks": _loads_json(r["query_toks"]),
            "query_toks_no_value": _loads_json(r["query_toks_no_value"]),
            "question_toks": _loads_json(r["question_toks"]),
        }
        return SpiderQuestion(
            id=int(r["id"]),
            db_id=str(r["db_id"]),
            question=str(r["question"]),
            gold_sql=str(r["query"]) if r["query"] is not None else None,
            source_file=str(r["source_file"]),
            source_index=int(r["source_index"]),
            meta=meta,
        )

    def get_tables(self, db_id: str, *, use_original: bool) -> List[TableRow]:
        field = "name_original" if use_original else "name"
        sql = f"""
        SELECT table_id, {field} AS tname
        FROM spider_tables
        WHERE db_id = ?
        ORDER BY table_id
        """
        rows = self.conn.execute(sql, (db_id,)).fetchall()
        return [TableRow(int(r["table_id"]), str(r["tname"])) for r in rows]

    def get_columns_by_table(self, db_id: str, *, use_original: bool) -> Dict[int, List[Tuple[str, str]]]:
        field = "name_original" if use_original else "name"
        sql = f"""
        SELECT table_id, {field} AS cname, col_type
        FROM spider_columns
        WHERE db_id = ? AND table_id IS NOT NULL
        ORDER BY table_id, column_id
        """
        rows = self.conn.execute(sql, (db_id,)).fetchall()
        out: Dict[int, List[Tuple[str, str]]] = {}
        for r in rows:
            tid = int(r["table_id"])
            out.setdefault(tid, []).append((str(r["cname"]), str(r["col_type"])))
        return out

    def get_primary_keys(self, db_id: str, *, use_original: bool) -> Dict[int, List[str]]:
        field = "name_original" if use_original else "name"
        sql = f"""
        SELECT c.table_id AS table_id, c.{field} AS cname
        FROM spider_primary_keys pk
        JOIN spider_columns c
          ON c.db_id = pk.db_id AND c.column_id = pk.column_id
        WHERE pk.db_id = ? AND c.table_id IS NOT NULL
        ORDER BY c.table_id, c.column_id
        """
        rows = self.conn.execute(sql, (db_id,)).fetchall()
        out: Dict[int, List[str]] = {}
        for r in rows:
            out.setdefault(int(r["table_id"]), []).append(str(r["cname"]))
        return out

    def get_foreign_keys(self, db_id: str, *, use_original: bool) -> List[ForeignKeyRow]:
        field = "name_original" if use_original else "name"
        sql = f"""
        SELECT
          c_from.table_id AS from_table_id,
          c_from.{field} AS from_col,
          c_to.table_id AS to_table_id,
          c_to.{field} AS to_col
        FROM spider_foreign_keys fk
        JOIN spider_columns c_from
          ON c_from.db_id = fk.db_id AND c_from.column_id = fk.from_column_id
        JOIN spider_columns c_to
          ON c_to.db_id = fk.db_id AND c_to.column_id = fk.to_column_id
        WHERE fk.db_id = ?
          AND c_from.table_id IS NOT NULL
          AND c_to.table_id IS NOT NULL
        """
        rows = self.conn.execute(sql, (db_id,)).fetchall()
        return [
            ForeignKeyRow(int(r["from_table_id"]), str(r["from_col"]), int(r["to_table_id"]), str(r["to_col"]))
            for r in rows
        ]


def _loads_json(v):
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return v
