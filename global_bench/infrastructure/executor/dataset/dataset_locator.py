from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class DatasetLocator:
    datasets_root: str  # ex: "datasets/test_database" or "datasets/database"

    def parquet_dir(self, db_id: str) -> str:
        return os.path.join(self.datasets_root, db_id)

    def sqlite_path(self, db_id: str) -> str:
        return os.path.join(self.datasets_root, db_id, f"{db_id}.sqlite")
