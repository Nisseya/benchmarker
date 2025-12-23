import os
import sqlite3
import pandas as pd
from uuid import uuid4
from typing import List
from domain.models.task import DataContext

class DatasetService:
    def __init__(self, repository):
        self.repository = repository

    def register_dataset(self, name: str, file_path: str) -> DataContext:
        """
        Analyse un fichier (CSV ou SQLite) et l'enregistre comme contexte de données.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Fichier non trouvé : {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        schema = {}

        if ext == ".sqlite":
            schema = self._extract_sqlite_schema(file_path)
        elif ext == ".csv":
            schema = self._extract_csv_schema(file_path)
        else:
            raise ValueError("Format non supporté. Utilisez .sqlite ou .csv")

        dataset = DataContext(
            id=uuid4(),
            name=name,
            schema_definition=schema,
            storage_link=os.path.abspath(file_path),
            is_active=True
        )

        self.repository.save_data_context(dataset)
        return dataset

    def _extract_sqlite_schema(self, path: str) -> dict:
        """Extrait la structure d'une base SQLite."""
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        db_schema = {}
        for (table_name,) in tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [{"name": col[1], "type": col[2]} for col in cursor.fetchall()]
            db_schema[table_name] = columns
        conn.close()
        return db_schema

    def _extract_csv_schema(self, path: str) -> dict:
        """Extrait les colonnes d'un CSV via Pandas."""
        df = pd.read_csv(path, nrows=1)
        return {
            "table_name": os.path.basename(path).split('.')[0],
            "columns": [{"name": col, "type": str(dtype)} for col, dtype in df.dtypes.items()]
        }

    def list_datasets(self) -> List[DataContext]:
        return self.repository.get_all_contexts()

    def delete_dataset(self, dataset_id: str):
        self.repository.delete_context(dataset_id)