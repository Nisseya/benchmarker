#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple


CATALOG_TABLES_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS spider_databases (
  db_id TEXT PRIMARY KEY,
  table_names TEXT NOT NULL,
  table_names_original TEXT NOT NULL,
  raw TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS spider_tables (
  db_id TEXT NOT NULL,
  table_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  name_original TEXT NOT NULL,
  PRIMARY KEY (db_id, table_id),
  FOREIGN KEY (db_id) REFERENCES spider_databases(db_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS spider_columns (
  db_id TEXT NOT NULL,
  column_id INTEGER NOT NULL,
  table_id INTEGER NULL,
  name TEXT NOT NULL,
  name_original TEXT NOT NULL,
  col_type TEXT NOT NULL,
  PRIMARY KEY (db_id, column_id),
  FOREIGN KEY (db_id) REFERENCES spider_databases(db_id) ON DELETE CASCADE,
  FOREIGN KEY (db_id, table_id) REFERENCES spider_tables(db_id, table_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS spider_primary_keys (
  db_id TEXT NOT NULL,
  column_id INTEGER NOT NULL,
  PRIMARY KEY (db_id, column_id),
  FOREIGN KEY (db_id) REFERENCES spider_databases(db_id) ON DELETE CASCADE,
  FOREIGN KEY (db_id, column_id) REFERENCES spider_columns(db_id, column_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS spider_foreign_keys (
  db_id TEXT NOT NULL,
  from_column_id INTEGER NOT NULL,
  to_column_id INTEGER NOT NULL,
  PRIMARY KEY (db_id, from_column_id, to_column_id),
  FOREIGN KEY (db_id) REFERENCES spider_databases(db_id) ON DELETE CASCADE,
  FOREIGN KEY (db_id, from_column_id) REFERENCES spider_columns(db_id, column_id) ON DELETE CASCADE,
  FOREIGN KEY (db_id, to_column_id) REFERENCES spider_columns(db_id, column_id) ON DELETE CASCADE
);
"""

QUESTIONS_DDL_TEMPLATE = """
CREATE TABLE IF NOT EXISTS {questions_table} (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  db_id TEXT NOT NULL,
  question TEXT NOT NULL,
  query TEXT NULL,
  sql_json TEXT NULL,
  query_toks TEXT NULL,
  query_toks_no_value TEXT NULL,
  question_toks TEXT NULL,
  source_file TEXT NOT NULL,
  source_index INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS {questions_table}_dbid_idx ON {questions_table}(db_id);
CREATE INDEX IF NOT EXISTS {questions_table}_source_idx ON {questions_table}(source_file, source_index);
"""


def dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def connect_sqlite(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_schema(conn: sqlite3.Connection, questions_table: str) -> None:
    conn.executescript(CATALOG_TABLES_DDL)
    conn.executescript(QUESTIONS_DDL_TEMPLATE.format(questions_table=questions_table))


def wipe_tables(conn: sqlite3.Connection, questions_table: str) -> None:
    # wipe in FK-safe order
    conn.execute(f"DELETE FROM {questions_table};")
    conn.execute("DELETE FROM spider_foreign_keys;")
    conn.execute("DELETE FROM spider_primary_keys;")
    conn.execute("DELETE FROM spider_columns;")
    conn.execute("DELETE FROM spider_tables;")
    conn.execute("DELETE FROM spider_databases;")


def ingest_tables_json(conn: sqlite3.Connection, tables_json_path: str) -> None:
    schemas = read_json(tables_json_path)
    if not isinstance(schemas, list):
        raise ValueError("tables.json must be a list of schema objects")

    with conn:

        # spider_databases
        conn.executemany(
            """
            INSERT OR REPLACE INTO spider_databases (db_id, table_names, table_names_original, raw)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    s["db_id"],
                    dumps(s["table_names"]),
                    dumps(s["table_names_original"]),
                    dumps(s),
                )
                for s in schemas
            ],
        )

        # spider_tables, spider_columns, pk, fk
        for s in schemas:
            db_id = s["db_id"]

            # tables
            table_rows = [
                (db_id, i, s["table_names"][i], s["table_names_original"][i])
                for i in range(len(s["table_names"]))
            ]
            conn.executemany(
                """
                INSERT OR REPLACE INTO spider_tables (db_id, table_id, name, name_original)
                VALUES (?, ?, ?, ?)
                """,
                table_rows,
            )

            # columns (flatten)
            col_rows = []
            for col_id, ((t_id, name), (_, name_orig), col_type) in enumerate(
                zip(s["column_names"], s["column_names_original"], s["column_types"])
            ):
                table_id = None if int(t_id) == -1 else int(t_id)
                col_rows.append((db_id, col_id, table_id, name, name_orig, col_type))

            conn.executemany(
                """
                INSERT OR REPLACE INTO spider_columns (db_id, column_id, table_id, name, name_original, col_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                col_rows,
            )

            # primary keys
            pk_rows = [(db_id, int(cid)) for cid in s.get("primary_keys", [])]
            if pk_rows:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO spider_primary_keys (db_id, column_id)
                    VALUES (?, ?)
                    """,
                    pk_rows,
                )

            # foreign keys
            fk_rows = [(db_id, int(a), int(b)) for a, b in s.get("foreign_keys", [])]
            if fk_rows:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO spider_foreign_keys (db_id, from_column_id, to_column_id)
                    VALUES (?, ?, ?)
                    """,
                    fk_rows,
                )



def _extract_sql_json(obj: Dict[str, Any]) -> Any:
    # Spider datasets sometimes use "sql", some forks use "sql_json"
    if "sql" in obj:
        return obj["sql"]
    if "sql_json" in obj:
        return obj["sql_json"]
    return None


def ingest_questions_json(
    conn: sqlite3.Connection,
    questions_table: str,
    dataset_path: str,
    source_file_label: Optional[str] = None,
) -> int:
    data = read_json(dataset_path)
    if not isinstance(data, list):
        raise ValueError(f"{dataset_path} must be a list of examples")

    label = source_file_label or os.path.basename(dataset_path)

    rows = []
    for idx, ex in enumerate(data):
        db_id = ex.get("db_id")
        question = ex.get("question")
        query = ex.get("query")
        if not db_id or not question:
            continue

        row = (
            db_id,
            question,
            query,
            dumps(_extract_sql_json(ex)) if _extract_sql_json(ex) is not None else None,
            dumps(ex.get("query_toks")) if ex.get("query_toks") is not None else None,
            dumps(ex.get("query_toks_no_value")) if ex.get("query_toks_no_value") is not None else None,
            dumps(ex.get("question_toks")) if ex.get("question_toks") is not None else None,
            label,
            idx,
        )
        rows.append(row)

    with conn:
        conn.executemany(
            f"""
            INSERT INTO {questions_table} (
            db_id, question, query,
            sql_json, query_toks, query_toks_no_value, question_toks,
            source_file, source_index
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def optimize_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute("ANALYZE;")
    conn.execute("VACUUM;")
    # Optional: WAL can increase speed but creates extra -wal file.
    # conn.execute("PRAGMA journal_mode=WAL;")


def main() -> None:
    p = argparse.ArgumentParser(description="Build a SQLite DB from Spider tables.json + dataset JSONs.")
    p.add_argument("--tables-json", required=True, help="Path to Spider tables.json")
    p.add_argument("--datasets", nargs="+", required=True, help="One or more Spider dataset JSON files")
    p.add_argument("--out", required=True, help="Output sqlite file path")
    p.add_argument("--questions-table", default="spider_benchmark_questions", help="Questions table name")
    p.add_argument("--wipe", action="store_true", help="Wipe existing data before ingest")
    args = p.parse_args()

    conn = connect_sqlite(args.out)
    try:
        create_schema(conn, args.questions_table)
        if args.wipe:
            wipe_tables(conn, args.questions_table)

        ingest_tables_json(conn, args.tables_json)

        total = 0
        for ds in args.datasets:
            total += ingest_questions_json(conn, args.questions_table, ds)

        optimize_sqlite(conn)

        print(f"✅ Built sqlite: {args.out}")
        print(f"✅ Ingested schemas from: {args.tables_json}")
        print(f"✅ Ingested questions: {total} (table={args.questions_table})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
