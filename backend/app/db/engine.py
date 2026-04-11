"""Database engine creation utilities."""

from functools import lru_cache

from sqlmodel import create_engine

from app.core.settings import get_settings


def build_database_url() -> str:
    return get_settings().database_url


@lru_cache(maxsize=1)
def create_db_engine():
    return create_engine(build_database_url(), echo=False)
