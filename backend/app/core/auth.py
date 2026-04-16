"""Authentication helpers for the backend API."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from uuid import UUID

import firebase_admin
import jwt
from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from app.models.models import User
from app.core.settings import Settings, get_settings


@dataclass(frozen=True)
class ExternalAuthPrincipal:
    firebase_uid: str
    email: str
    name: str | None


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: UUID
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


def _external_principal_from_dev_token(token: str) -> ExternalAuthPrincipal:
    trimmed = token.strip()
    if not trimmed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty dev token")
    if trimmed.count(".") == 2:
        try:
            _header, payload_b64, _signature = trimmed.split(".")
            padding = "=" * (-len(payload_b64) % 4)
            payload_raw = base64.urlsafe_b64decode(f"{payload_b64}{padding}")
            payload = json.loads(payload_raw.decode("utf-8"))
            uid = str(payload.get("user_id") or payload.get("sub") or "").strip()
            email = str(payload.get("email") or "").strip()
            name = str(payload.get("name") or "").strip() or None
            if uid and email:
                return ExternalAuthPrincipal(firebase_uid=uid, email=email, name=name)
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
    if "|" in trimmed:
        uid, email, *rest = trimmed.split("|")
        name = rest[0] if rest else None
    else:
        uid = trimmed
        email = f"{uid}@sutra.dev"
        name = "Dev User"
    return ExternalAuthPrincipal(firebase_uid=uid, email=email, name=name)


def _external_principal_from_verified_token(token: str) -> ExternalAuthPrincipal:
    _get_firebase_app()
    decoded = firebase_auth.verify_id_token(token)
    email = (decoded.get("email") or "").strip()
    uid = (decoded.get("uid") or "").strip()
    if not uid or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token missing uid/email",
        )
    if decoded.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase email is not verified",
        )
    return ExternalAuthPrincipal(
        firebase_uid=uid,
        email=email,
        name=(decoded.get("name") or "").strip() or None,
    )


def authenticate_external_principal(token: str, settings: Settings) -> ExternalAuthPrincipal:
    if settings.dev_auth_bypass:
        return _external_principal_from_dev_token(token)
    try:
        return _external_principal_from_verified_token(token)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def issue_access_token(user: User, settings: Settings) -> tuple[str, int]:
    expires_in = settings.jwt_expiration_seconds
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), expires_in


def _principal_from_access_token(token: str, settings: Settings) -> AuthPrincipal:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc

    subject = str(payload.get("sub") or "").strip()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token missing subject",
        )

    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token subject is invalid",
        ) from exc

    return AuthPrincipal(
        user_id=user_id,
        email=str(payload.get("email") or "").strip(),
        name=(str(payload.get("name") or "").strip() or None),
    )


def get_current_principal(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> AuthPrincipal:
    token = _parse_bearer_token(authorization)
    return _principal_from_access_token(token, settings)
