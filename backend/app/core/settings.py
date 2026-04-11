"""Runtime settings for the backend app."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _repo_backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


load_dotenv(_repo_backend_dir() / ".env")


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    hermes_homes_root: Path
    hermes_homes_root_is_configured: bool
    firebase_service_account_json: str | None
    dev_auth_bypass: bool
    frontend_url: str | None
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    jwt_expiration_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "dev").strip().lower() or "dev"
    raw_db_url = os.getenv("POSTGRES_URL")
    if not raw_db_url:
        raise RuntimeError("Missing database URL. Set POSTGRES_URL in backend/.env.")

    configured_homes_root = os.getenv("SUTRA_HERMES_HOMES_ROOT", "").strip()
    homes_root = configured_homes_root
    if not homes_root:
        homes_root = str((_repo_backend_dir() / ".sutra" / "hermes-homes").resolve())

    firebase_json = (
        os.getenv("SUTRA_FIREBASE_SERVICE_ACCOUNT_JSON")
        or os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        or ""
    ).strip() or None
    jwt_secret = (os.getenv("SUTRA_JWT_SECRET") or "").strip()
    if not jwt_secret:
        raise RuntimeError("Missing JWT secret. Set SUTRA_JWT_SECRET in backend/.env.")
    if len(jwt_secret) < 32:
        raise RuntimeError("SUTRA_JWT_SECRET must be at least 32 characters long.")

    return Settings(
        app_env=app_env,
        database_url=_normalize_database_url(raw_db_url),
        hermes_homes_root=Path(homes_root).expanduser().resolve(),
        hermes_homes_root_is_configured=bool(configured_homes_root),
        firebase_service_account_json=firebase_json,
        dev_auth_bypass=os.getenv("SUTRA_DEV_AUTH_BYPASS", "false").lower() in {"1", "true", "yes"},
        frontend_url=(os.getenv("SUTRA_FRONTEND_URL") or "").strip() or None,
        jwt_secret=jwt_secret,
        jwt_issuer=(os.getenv("SUTRA_JWT_ISSUER") or "sutra-backend").strip(),
        jwt_audience=(os.getenv("SUTRA_JWT_AUDIENCE") or "sutra-api").strip(),
        jwt_expiration_seconds=max(int(os.getenv("SUTRA_JWT_EXPIRATION_SECONDS", "86400")), 60),
    )
