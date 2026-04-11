"""Small helper functions shared by route modules."""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from app.models.models import Agent


def list_agents_for_user(session: Session, user_id: UUID) -> list[Agent]:
    return list(
        session.exec(
            select(Agent).where(Agent.user_id == user_id).order_by(Agent.created_at.asc())
        ).all()
    )
