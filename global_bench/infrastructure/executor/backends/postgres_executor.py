from __future__ import annotations
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

import psycopg2

from domain.ports.executor import ExecutorPort, ExecutionResult

@dataclass(frozen=True)
class PostgresExecutorConfig:
    timeout_ms: int = 2500
    max_rows: int = 2000
    read_only: bool = True
    set_statement_timeout: bool = True

class PostgresExecutor(ExecutorPort):
    def __init__(self, config: PostgresExecutorConfig | None = None):
        self.config = config or PostgresExecutorConfig()

    def execute(self, code: str, db_id: str, context: Dict[str, Any]) -> ExecutionResult:
        t0 = time.perf_counter()

        dsn = context.get("dsn")
        dsn_base = context.get("dsn_base")
        host = context.get("host")
        port = context.get("port")
        user = context.get("user")
        password = context.get("password")

        params = context.get("params", None)
        search_path = context.get("search_path", None)

        conn = None
        try:
            if dsn:
                conn = psycopg2.connect(dsn, dbname=db_id)
            elif dsn_base:
                conn = psycopg2.connect(dsn_base + f" dbname={db_id}")
            elif host and user:
                conn = psycopg2.connect(
                    host=host,
                    port=port or 5432,
                    user=user,
                    password=password,
                    dbname=db_id,
                )
            else:
                return ExecutionResult(
                    success=False,
                    output=None,
                    captured_state={"db_id": db_id},
                    execution_time_ms=0.0,
                    memory_peak_mb=0.0,
                    error="Missing postgres connection info in context (dsn|dsn_base|host+user)",
                )

            conn.autocommit = False

            with conn.cursor() as cur:
                if self.config.read_only:
                    cur.execute("BEGIN READ ONLY;")
                else:
                    cur.execute("BEGIN;")

                if search_path:
                    cur.execute("SET LOCAL search_path TO " + ",".join([s.strip() for s in str(search_path).split(",")]))

                if self.config.set_statement_timeout:
                    cur.execute("SET LOCAL statement_timeout = %s;", (self.config.timeout_ms,))

                cur.execute(code, params)

                rows: list[tuple[Any, ...]] = []
                cols: list[str] = []
                if cur.description:
                    cols = [d.name for d in cur.description]

                    fetched = 0
                    while True:
                        batch = cur.fetchmany(200)
                        if not batch:
                            break
                        rows.extend(batch)
                        fetched += len(batch)
                        if fetched >= self.config.max_rows:
                            break

                conn.rollback()

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return ExecutionResult(
                success=True,
                output=rows,
                captured_state={"db_id": db_id, "row_count": len(rows), "columns": cols},
                execution_time_ms=elapsed_ms,
                memory_peak_mb=0.0,
                error=None,
            )

        except Exception as e:
            try:
                if conn:
                    conn.rollback()
            except Exception:
                pass

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return ExecutionResult(
                success=False,
                output=None,
                captured_state={"db_id": db_id},
                execution_time_ms=elapsed_ms,
                memory_peak_mb=0.0,
                error=f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            )
        finally:
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
