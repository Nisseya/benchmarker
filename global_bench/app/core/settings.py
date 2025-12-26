from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pg_dsn:str = os.getenv("PG_DSN") or os.getenv("DATABASE_URL") or ""
    datasets_root: str = "datasets/test_database"
    worker_base_url: str = os.getenv("WORKER_BASE_URL") or "http://localhost:8001"

    dtype: str = "auto"
