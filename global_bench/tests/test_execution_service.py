# tests/test_execution_service.py
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
import polars as pl

from domain.services.execution_service import ExecutionService


def _write_parquet_dataset(root: Path, db_id: str) -> None:
    db_dir = root / db_id
    db_dir.mkdir(parents=True, exist_ok=True)

    (pl.DataFrame({"customer_id": [1, 2, 3], "name": ["a", "b", "c"]})
     .write_parquet(db_dir / "customers.parquet"))

    (pl.DataFrame({"order_id": [10, 11, 12, 13], "customer_id": [1, 1, 2, 1]})
     .write_parquet(db_dir / "orders.parquet"))


def _write_sqlite_dataset(root: Path, db_id: str) -> None:
    db_dir = root / db_id
    db_dir.mkdir(parents=True, exist_ok=True)

    db_path = db_dir / f"{db_id}.sqlite"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT);")
        cur.execute("CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER);")
        cur.executemany(
            "INSERT INTO customers(customer_id, name) VALUES (?, ?);",
            [(1, "a"), (2, "b"), (3, "c")],
        )
        cur.executemany(
            "INSERT INTO orders(order_id, customer_id) VALUES (?, ?);",
            [(10, 1), (11, 1), (12, 2), (13, 1)],
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def datasets_root(tmp_path: Path) -> Path:
    return tmp_path / "datasets"


def test_execution_service_polars_reads_tables_and_returns_df(datasets_root: Path) -> None:
    db_id = "shop_1"
    _write_parquet_dataset(datasets_root, db_id)

    svc = ExecutionService(datasets_root=str(datasets_root))

    code = """
# tables injected by executor: customers, orders (polars DataFrames)
result = (
    orders.join(customers, on="customer_id")
    .group_by("customer_id")
    .agg(pl.len().alias("n_orders"))
    .sort("customer_id")
)
"""

    resp = svc.execute(executor_kind="polars", db_id=db_id, code=code, context={})

    assert resp.executor_kind == "polars"
    assert resp.db_id == db_id
    assert resp.result.success is True
    assert isinstance(resp.result.output, pl.DataFrame)

    out = resp.result.output
    assert out.columns == ["customer_id", "n_orders"]
    assert out.to_dicts() == [
        {"customer_id": 1, "n_orders": 3},
        {"customer_id": 2, "n_orders": 1},
    ]


def test_execution_service_python_reads_tables_and_returns_scalar(datasets_root: Path) -> None:
    db_id = "shop_2"
    _write_parquet_dataset(datasets_root, db_id)

    svc = ExecutionService(datasets_root=str(datasets_root))

    code = """
# customers, orders injected as polars DataFrames
result = orders.shape[0] + customers.shape[0]
"""

    resp = svc.execute(executor_kind="python", db_id=db_id, code=code, context={})

    assert resp.result.success is True
    assert resp.result.output == 4 + 3  # 4 orders + 3 customers


def test_execution_service_sqlite_executes_query_and_returns_rows(datasets_root: Path) -> None:
    db_id = "shop_sqlite"
    _write_sqlite_dataset(datasets_root, db_id)

    svc = ExecutionService(datasets_root=str(datasets_root))

    code = """
SELECT customer_id, COUNT(*) AS n_orders
FROM orders
GROUP BY customer_id
ORDER BY customer_id;
""".strip()

    resp = svc.execute(executor_kind="sqlite", db_id=db_id, code=code, context={})

    assert resp.result.success is True
    assert isinstance(resp.result.output, list)
    assert resp.result.output == [(1, 3), (2, 1)]


@pytest.mark.skipif(
    os.getenv("PG_DSN_BASE") is None and os.getenv("PG_HOST") is None,
    reason="Set PG_DSN_BASE='host=... user=... password=... port=...' or PG_HOST/PG_USER/PG_PASSWORD to run",
)
def test_execution_service_postgres_executes_query(datasets_root: Path) -> None:
    # Postgres executor uses db_id as the database name.
    # Provide either:
    # - PG_DSN_BASE="host=... port=... user=... password=... sslmode=disable"
    # or
    # - PG_HOST, PG_PORT, PG_USER, PG_PASSWORD
    db_id = os.getenv("PG_DB", "postgres")

    svc = ExecutionService(datasets_root=str(datasets_root))

    context = {}
    if os.getenv("PG_DSN_BASE"):
        context["dsn_base"] = os.getenv("PG_DSN_BASE")
    else:
        context["host"] = os.getenv("PG_HOST")
        context["port"] = int(os.getenv("PG_PORT", "5432"))
        context["user"] = os.getenv("PG_USER")
        context["password"] = os.getenv("PG_PASSWORD")

    resp = svc.execute(
        executor_kind="postgres",
        db_id=db_id,
        code="SELECT 1;",
        context=context,
    )

    assert resp.result.success is True
    assert resp.result.output == [(1,)]
