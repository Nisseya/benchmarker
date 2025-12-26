from __future__ import annotations
from typing import Literal

from infrastructure.executor.dataset.dataset_locator import DatasetLocator
from infrastructure.executor.backends.python_executor import PythonExecutor, PythonExecutorConfig
from infrastructure.executor.backends.polars_executor import PolarsExecutor, PolarsExecutorConfig
from infrastructure.executor.backends.sqlite_executor import SqliteExecutor, SqliteExecutorConfig
from infrastructure.executor.backends.postgres_executor import PostgresExecutor, PostgresExecutorConfig

ExecutorKind = Literal["python", "polars", "sqlite", "postgres"]

def make_executor(kind: ExecutorKind, locator: DatasetLocator):
    if kind == "python":
        return PythonExecutor(locator, PythonExecutorConfig())
    if kind == "polars":
        return PolarsExecutor(locator, PolarsExecutorConfig())
    if kind == "sqlite":
        return SqliteExecutor(locator, SqliteExecutorConfig())
    if kind == "postgres":
        return PostgresExecutor(PostgresExecutorConfig())
    raise ValueError(f"Unknown executor kind: {kind}")
