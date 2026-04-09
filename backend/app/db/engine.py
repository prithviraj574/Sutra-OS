"""Database engine creation utilities."""

import os

from sqlmodel import create_engine

DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sutra"


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def build_database_url() -> str:
    raw = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL") or DEFAULT_DB_URL
    return normalize_database_url(raw)


def create_db_engine():
    return create_engine(build_database_url(), echo=False)

