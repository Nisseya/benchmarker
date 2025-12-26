from __future__ import annotations
import sqlite3
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict

from domain.ports.executor import ExecutorPort, ExecutionResult
from infrastructure.executor.dataset.dataset_locator import DatasetLocator

@dataclass(frozen=True)
class SqliteExecutorConfig:
    timeout_ms: int = 2500
    max_rows: int = 2000

class SqliteExecutor(ExecutorPort):
    def __init__(self, locator: DatasetLocator, config: SqliteExecutorConfig | None = None):
        self.locator = locator
        self.config = config or SqliteExecutorConfig()

    def execute(self, code: str, db_id: str, context: Dict[str, Any]) -> ExecutionResult:
        t0 = time.perf_counter()
        sqlite_path = self.locator.sqlite_path(db_id)

        try:
            conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True, check_same_thread=False)
            conn.row_factory = sqlite3.Row

            deadline = time.perf_counter() + self.config.timeout_ms / 1000.0

            def progress_handler() -> int:
                return 1 if time.perf_counter() > deadline else 0

            conn.set_progress_handler(progress_handler, 10000)

            cur = conn.cursor()
            cur.execute(code)

            rows: list[tuple[Any, ...]] = []
            cols: list[str] = []
            if cur.description:
                cols = [d[0] for d in cur.description]

            fetched = 0
            while True:
                batch = cur.fetchmany(200)
                if not batch:
                    break
                rows.extend(tuple(r) for r in batch)
                fetched += len(batch)
                if fetched >= self.config.max_rows:
                    break

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return ExecutionResult(
                success=True,
                output=rows,
                captured_state={"db_id": db_id, "row_count": len(rows), "columns": cols},
                execution_time_ms=elapsed_ms,
                memory_peak_mb=0.0,
                error=None,
            )

        except sqlite3.OperationalError as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            msg = str(e)
            if "interrupted" in msg.lower():
                msg = "timeout"
            return ExecutionResult(
                success=False,
                output=None,
                captured_state={"db_id": db_id},
                execution_time_ms=elapsed_ms,
                memory_peak_mb=0.0,
                error=msg,
            )

        except Exception as e:
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
                conn.close()
            except Exception:
                pass
