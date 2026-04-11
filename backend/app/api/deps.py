"""Shared FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.core.auth import AuthPrincipal, get_current_principal
from app.core.settings import Settings, get_settings
from app.db.session import get_session_factory

SessionDep = Annotated[Session, Depends(get_session_factory())]
PrincipalDep = Annotated[AuthPrincipal, Depends(get_current_principal)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
