"""Shared FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.auth import AuthPrincipal, get_current_principal
from app.core.settings import Settings, get_settings
from app.db.session import get_session_factory
from app.models.models import User

SessionDep = Annotated[Session, Depends(get_session_factory())]
PrincipalDep = Annotated[AuthPrincipal, Depends(get_current_principal)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_current_user(
    session: SessionDep,
    principal: PrincipalDep,
) -> User:
    user = session.exec(
        select(User).where(User.id == principal.user_id)
    ).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
