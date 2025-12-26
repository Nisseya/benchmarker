from __future__ import annotations
import time
import traceback
import tracemalloc
from dataclasses import dataclass
from typing import Any, Dict, Optional

import polars as pl

from domain.ports.executor import ExecutorPort, ExecutionResult
from infrastructure.executor.dataset.dataset_locator import DatasetLocator
from infrastructure.executor.dataset.parquet_loader import load_parquet_tables, ParquetLoadConfig

@dataclass(frozen=True)
class PythonExecutorConfig:
    timeout_ms: int = 3000
    capture_all_locals: bool = True
    capture_keys: Optional[list[str]] = None
    forbid_imports: bool = False
    parquet_eager: bool = True

class PythonExecutor(ExecutorPort):
    def __init__(self, locator: DatasetLocator, config: PythonExecutorConfig | None = None):
        self.locator = locator
        self.config = config or PythonExecutorConfig()

    def execute(self, code: str, db_id: str, context: Dict[str, Any]) -> ExecutionResult:
        t0 = time.perf_counter()
        tracemalloc.start()

        globals_dict: Dict[str, Any] = {"__builtins__": __builtins__}
        if self.config.forbid_imports:
            b = dict(__builtins__.__dict__)
            b["__import__"] = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Imports are disabled."))
            globals_dict["__builtins__"] = b

        locals_dict: Dict[str, Any] = dict(context)
        locals_dict["db_id"] = db_id
        locals_dict["pl"] = pl

        parquet_dir = self.locator.parquet_dir(db_id)
        tables = load_parquet_tables(parquet_dir, ParquetLoadConfig(eager=self.config.parquet_eager))
        locals_dict.update(tables)
        locals_dict["tables"] = tables

        try:
            compiled = compile(code, "<python_executor>", "exec")

            def _guard() -> None:
                if (time.perf_counter() - t0) * 1000.0 > self.config.timeout_ms:
                    raise TimeoutError(f"Execution timed out after {self.config.timeout_ms} ms")

            _guard()
            exec(compiled, globals_dict, locals_dict)
            _guard()

            output = locals_dict.get("result", locals_dict.get("output", None))

            cur, peak = tracemalloc.get_traced_memory()
            peak_mb = float(peak) / (1024.0 * 1024.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            return ExecutionResult(
                success=True,
                output=output,
                captured_state=self._capture_state(locals_dict),
                execution_time_ms=elapsed_ms,
                memory_peak_mb=peak_mb,
                error=None,
            )

        except Exception as e:
            cur, peak = tracemalloc.get_traced_memory()
            peak_mb = float(peak) / (1024.0 * 1024.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            return ExecutionResult(
                success=False,
                output=None,
                captured_state=self._capture_state(locals_dict),
                execution_time_ms=elapsed_ms,
                memory_peak_mb=peak_mb,
                error=f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            )
        finally:
            tracemalloc.stop()

    def _capture_state(self, locals_dict: Dict[str, Any]) -> Dict[str, Any]:
        if self.config.capture_keys is not None:
            return {k: locals_dict.get(k) for k in self.config.capture_keys if k in locals_dict}
        if not self.config.capture_all_locals:
            return {}

        state: Dict[str, Any] = {}
        for k, v in locals_dict.items():
            if k.startswith("__") or k in ("pl",):
                continue
            if callable(v) or hasattr(v, "__spec__"):
                continue
            if isinstance(v, (pl.DataFrame, pl.LazyFrame)):
                try:
                    state[k] = {"__type__": "DataFrame", "shape": v.shape, "columns": v.columns}
                except Exception:
                    state[k] = {"__type__": type(v).__name__}
                continue
            state[k] = v
        return state
