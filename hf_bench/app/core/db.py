from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse


DB_URL = os.getenv("DB_URL", "sqlite:////app/data/hf_bench.sqlite")


def _sqlite_path_from_url(db_url: str) -> Path:
    # Accepts:
    # - sqlite:////abs/path.db
    # - sqlite:///abs/path.db
    # - sqlite:relative/path.db  (not recommended but handled)
    if not db_url.startswith("sqlite:"):
        raise ValueError("Only sqlite is supported. Use DB_URL=sqlite:////path/to/db.sqlite")

    parsed = urlparse(db_url)
    # For sqlite URLs, netloc is usually empty. The absolute path is in parsed.path.
    raw_path = parsed.path or db_url.replace("sqlite:", "", 1)

    p = Path(raw_path)
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    else:
        p = p.resolve()

    return p


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    p = _sqlite_path_from_url(DB_URL)
    if not p.exists():
        raise FileNotFoundError(f"SQLite DB not found: {p}")

    # Valid sqlite URI: file:///abs/path?mode=ro
    uri = p.as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
    finally:
        conn.close()
