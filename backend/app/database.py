import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlmodel import Session, create_engine

load_dotenv()

DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sutra"


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = normalize_database_url(
    os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL") or DEFAULT_DB_URL
)

engine = create_engine(DATABASE_URL, echo=False)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
