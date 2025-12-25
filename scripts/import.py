from __future__ import annotations

import argparse
import json

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import psycopg2
from psycopg2.extras import execute_values, Json

@dataclass(frozen=True)
class SpiderRow:
    db_id: str
    question: str
    query: str
    query_toks: List[str]
    query_toks_no_value: List[str]
    question_toks: List[str]
    sql: Dict[str, Any]
    source_file: str
    source_index: int


DDL_POSTGRES = """
CREATE TABLE IF NOT EXISTS {table_ident} (
    id BIGSERIAL PRIMARY KEY,
    db_id TEXT NOT NULL,
    question TEXT NOT NULL,
    query TEXT NOT NULL,
    query_toks JSONB NOT NULL,
    query_toks_no_value JSONB NOT NULL,
    question_toks JSONB NOT NULL,
    sql_json JSONB NOT NULL,
    source_file TEXT NOT NULL,
    source_index INTEGER NOT NULL,
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS {table_dbid_idx} ON {table_ident} (db_id);
CREATE INDEX IF NOT EXISTS {table_source_idx} ON {table_ident} (source_file, source_index);
"""



INSERT_SQL = """
INSERT INTO {table_ident} (
    db_id, question, query,
    query_toks, query_toks_no_value, question_toks,
    sql_json, source_file, source_index, inserted_at
)
VALUES %s
"""


def _read_json_file(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array (list). Got: {type(data).__name__}")
    return data


def _coerce_list_of_str(value: Any, field: str, ctx: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError(f"{ctx}: field '{field}' must be a list[str]. Got: {type(value).__name__}")
    return value


def _coerce_dict(value: Any, field: str, ctx: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{ctx}: field '{field}' must be an object/dict. Got: {type(value).__name__}")
    return value


def _parse_rows(records: List[Dict[str, Any]], source_file: str) -> List[SpiderRow]:
    rows: List[SpiderRow] = []
    for i, r in enumerate(records):
        ctx = f"{source_file}[{i}]"
        if not isinstance(r, dict):
            raise ValueError(f"{ctx}: each item must be an object/dict. Got: {type(r).__name__}")

        db_id = r.get("db_id")
        question = r.get("question")
        query = r.get("query")

        if not isinstance(db_id, str) or not db_id:
            raise ValueError(f"{ctx}: missing/invalid 'db_id'")
        if not isinstance(question, str) or not question:
            raise ValueError(f"{ctx}: missing/invalid 'question'")
        if not isinstance(query, str) or not query:
            raise ValueError(f"{ctx}: missing/invalid 'query'")

        query_toks = _coerce_list_of_str(r.get("query_toks", []), "query_toks", ctx)
        query_toks_no_value = _coerce_list_of_str(r.get("query_toks_no_value", []), "query_toks_no_value", ctx)
        question_toks = _coerce_list_of_str(r.get("question_toks", []), "question_toks", ctx)
        sql = _coerce_dict(r.get("sql", {}), "sql", ctx)

        rows.append(
            SpiderRow(
                db_id=db_id,
                question=question,
                query=query,
                query_toks=query_toks,
                query_toks_no_value=query_toks_no_value,
                question_toks=question_toks,
                sql=sql,
                source_file=source_file,
                source_index=i,
            )
        )
    return rows


def _safe_table_ident(table: str) -> str:
    parts = table.split(".")
    if len(parts) not in (1, 2):
        raise ValueError("table must be 'table' or 'schema.table'")
    def quote_ident(p: str) -> str:
        if not p or any(c in p for c in ['"', ";", " "]):
            raise ValueError(f"Unsafe identifier part: {p!r}")
        return '"' + p.replace('"', '""') + '"'
    return ".".join(quote_ident(p) for p in parts)


def ensure_table(conn, table: str) -> None:
    table_ident = _safe_table_ident(table)
    ddl = DDL_POSTGRES.format(
        table_ident=table_ident,
        table_dbid_idx=f"{table}_dbid_idx",
        table_source_idx=f"{table}_source_idx",
    )

    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()


def insert_rows(conn, table: str, rows: List[SpiderRow], batch_size: int = 5000) -> int:
    if not rows:
        return 0

    table_ident = _safe_table_ident(table)
    inserted_at = datetime.now(timezone.utc)

    total = 0
    with conn.cursor() as cur:
        for start in range(0, len(rows), batch_size):
            chunk = rows[start:start + batch_size]
            values: List[Tuple[Any, ...]] = []
            for r in chunk:
                values.append(
                    (
                        r.db_id,
                        r.question,
                        r.query,
                        Json(r.query_toks),
                        Json(r.query_toks_no_value),
                        Json(r.question_toks),
                        Json(r.sql),
                        r.source_file,
                        r.source_index,
                        inserted_at,
                    )
                )
            q = INSERT_SQL.format(table_ident=table_ident)
            execute_values(cur, q, values, page_size=min(batch_size, 2000))
            total += len(chunk)
    conn.commit()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Spider-style JSON arrays into PostgreSQL.")
    parser.add_argument("--db-url", required=True, help="PostgreSQL URL, e.g. postgresql://user:pass@host:5432/db")
    parser.add_argument("--table", default="spider_examples", help="Target table name (optionally schema.table)")
    parser.add_argument("--batch-size", type=int, default=5000, help="Insert batch size")
    parser.add_argument("--strict", action="store_true", help="Fail fast on first invalid record (default).")
    parser.add_argument("--skip-bad", action="store_true", help="Skip invalid records instead of failing.")
    parser.add_argument("json_files", nargs="+", help="Paths to JSON files (each must be a JSON array).")

    args = parser.parse_args()
    if args.strict and args.skip_bad:
        raise SystemExit("Choose either --strict or --skip-bad, not both.")

    json_paths = [Path(p) for p in args.json_files]
    for p in json_paths:
        if not p.exists():
            raise SystemExit(f"File not found: {p}")

    conn = psycopg2.connect(args.db_url)

    try:
        ensure_table(conn, args.table)

        all_rows: List[SpiderRow] = []
        bad = 0

        for p in json_paths:
            records = _read_json_file(p)
            try:
                rows = _parse_rows(records, source_file=str(p))
                all_rows.extend(rows)
            except Exception as e:
                if args.skip_bad:
                    bad += 1
                    print(f"[SKIP FILE] {p}: {e}")
                    continue
                raise

        inserted = insert_rows(conn, args.table, all_rows, batch_size=args.batch_size)
        print(f"Inserted rows: {inserted}")
        if bad:
            print(f"Skipped files: {bad}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
