from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Any, Iterable

import polars as pl

@dataclass(frozen=True)
class ParquetLoadConfig:
    eager: bool = True  # True => DataFrame, False => LazyFrame

def _table_name_from_path(p: str) -> str:
    base = os.path.basename(p)
    if base.lower().endswith(".parquet"):
        base = base[:-8]
    return base

def load_parquet_tables(parquet_dir: str, cfg: ParquetLoadConfig) -> Dict[str, Any]:
    if not os.path.isdir(parquet_dir):
        raise FileNotFoundError(f"Parquet dataset dir not found: {parquet_dir}")

    out: Dict[str, Any] = {}
    for name in sorted(os.listdir(parquet_dir)):
        if not name.lower().endswith(".parquet"):
            continue
        path = os.path.join(parquet_dir, name)
        table = _table_name_from_path(path)

        if cfg.eager:
            out[table] = pl.read_parquet(path)
        else:
            out[table] = pl.scan_parquet(path)

    return out
