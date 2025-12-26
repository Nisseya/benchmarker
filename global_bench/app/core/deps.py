from __future__ import annotations

from functools import lru_cache
from app.core.settings import Settings
from app.core.container import Container


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_container() -> Container:
    return Container(get_settings())
