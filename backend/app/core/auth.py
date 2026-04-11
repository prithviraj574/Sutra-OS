"""Authentication helpers for the backend API."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import firebase_admin
from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from app.core.settings import Settings, get_settings


@dataclass(frozen=True)
class AuthPrincipal:
    firebase_uid: str
    email: str
    name: str | None


def _parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected Bearer token",
        )
    return token.strip()


@lru_cache(maxsize=1)
def _get_firebase_app():
    settings = get_settings()
    if not settings.firebase_service_account_json:
        raise RuntimeError("Firebase service account JSON is not configured")

    cert_path = Path(settings.firebase_service_account_json)
    if not cert_path.is_absolute():
        cert_path = Path(__file__).resolve().parents[2] / cert_path
    if not cert_path.exists():
        raise RuntimeError(f"Firebase service account JSON not found at {cert_path}")

    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app(credentials.Certificate(str(cert_path)))


def _principal_from_dev_token(token: str) -> AuthPrincipal:
    trimmed = token.strip()
    if not trimmed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty dev token")
    if "|" in trimmed:
        uid, email, *rest = trimmed.split("|")
        name = rest[0] if rest else None
    else:
        uid = trimmed
        email = f"{uid}@sutra.dev"
        name = "Dev User"
    return AuthPrincipal(firebase_uid=uid, email=email, name=name)


def _principal_from_verified_token(token: str) -> AuthPrincipal:
    _get_firebase_app()
    decoded = firebase_auth.verify_id_token(token)
    email = (decoded.get("email") or "").strip()
    uid = (decoded.get("uid") or "").strip()
    if not uid or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token missing uid/email",
        )
    return AuthPrincipal(
        firebase_uid=uid,
        email=email,
        name=(decoded.get("name") or "").strip() or None,
    )


def get_current_principal(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> AuthPrincipal:
    token = _parse_bearer_token(authorization)
    if settings.dev_auth_bypass:
        return _principal_from_dev_token(token)
    return _principal_from_verified_token(token)
