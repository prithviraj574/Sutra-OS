from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _clear_runtime_caches() -> None:
    from app.core.auth import _get_firebase_app
    from app.core.settings import get_settings
    from app.db.engine import create_db_engine

    get_settings.cache_clear()
    create_db_engine.cache_clear()
    _get_firebase_app.cache_clear()


@pytest.fixture(scope="session")
def app_ctx(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    test_root = tmp_path_factory.mktemp("sutra-backend-tests")
    db_path = test_root / "sutra.sqlite3"
    homes_root = test_root / "homes"
    homes_root.mkdir(parents=True, exist_ok=True)

    keys = (
        "APP_ENV",
        "POSTGRES_URL",
        "SUTRA_DEV_AUTH_BYPASS",
        "SUTRA_JWT_SECRET",
        "SUTRA_JWT_ISSUER",
        "SUTRA_JWT_AUDIENCE",
        "SUTRA_JWT_EXPIRATION_SECONDS",
        "SUTRA_HERMES_HOMES_ROOT",
    )
    previous = {key: os.environ.get(key) for key in keys}

    os.environ["APP_ENV"] = "test"
    os.environ["POSTGRES_URL"] = f"sqlite:///{db_path}"
    os.environ["SUTRA_DEV_AUTH_BYPASS"] = "true"
    os.environ["SUTRA_JWT_SECRET"] = "sutra-tests-secret-should-be-at-least-32"
    os.environ["SUTRA_JWT_ISSUER"] = "sutra-tests"
    os.environ["SUTRA_JWT_AUDIENCE"] = "sutra-tests-aud"
    os.environ["SUTRA_JWT_EXPIRATION_SECONDS"] = "3600"
    os.environ["SUTRA_HERMES_HOMES_ROOT"] = str(homes_root)

    _clear_runtime_caches()
    from app.main import create_app
    from app.db.engine import create_db_engine
    from app.models.models import SQLModel

    app = create_app()
    engine = create_db_engine()
    SQLModel.metadata.create_all(engine)

    try:
        yield {"app": app, "engine": engine, "homes_root": homes_root}
    finally:
        engine.dispose()
        _clear_runtime_caches()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture()
def clean_state(app_ctx: dict[str, Any]) -> dict[str, Any]:
    from app.models.models import SQLModel

    engine = app_ctx["engine"]
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    homes_root: Path = app_ctx["homes_root"]
    if homes_root.exists():
        shutil.rmtree(homes_root)
    homes_root.mkdir(parents=True, exist_ok=True)
    return app_ctx


@pytest.fixture()
def app(clean_state: dict[str, Any]) -> FastAPI:
    return clean_state["app"]


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db_session(clean_state: dict[str, Any]) -> Session:
    with Session(clean_state["engine"]) as session:
        yield session


@pytest.fixture()
def settings():
    from app.core.settings import get_settings

    return get_settings()
