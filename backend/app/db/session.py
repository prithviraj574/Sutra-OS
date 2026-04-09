"""Session factory utilities."""

from collections.abc import Generator

from sqlmodel import Session

from .engine import create_db_engine


def get_session_factory():
    engine = create_db_engine()

    def _session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    return _session
