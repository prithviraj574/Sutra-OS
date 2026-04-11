"""User-facing provisioning services."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.auth import AuthPrincipal
from app.core.settings import Settings
from app.models.models import Agent, User
from app.services.hermes_home import ProvisionHermesHomeService


class EnsureUserService:
    def __init__(self, session: Session):
        self._session = session

    def ensure(self, principal: AuthPrincipal) -> User:
        user = self._session.exec(
            select(User).where(User.firebase_uid == principal.firebase_uid)
        ).one_or_none()
        if user is None:
            try:
                user = User(
                    firebase_uid=principal.firebase_uid,
                    email=principal.email,
                    name=principal.name,
                )
                self._session.add(user)
                self._session.flush()
                return user
            except IntegrityError:
                self._session.rollback()
                user = self._session.exec(
                    select(User).where(User.firebase_uid == principal.firebase_uid)
                ).one()

        user.email = principal.email
        user.name = principal.name
        self._session.add(user)
        self._session.flush()
        return user


class CreateAgentService:
    def __init__(self, session: Session, settings: Settings):
        self._session = session
        self._homes = ProvisionHermesHomeService(settings)

    def create(self, *, user_id: UUID, name: str) -> Agent:
        trimmed_name = name.strip()
        if not trimmed_name:
            raise ValueError("Agent name cannot be empty")
        agent = Agent(
            user_id=user_id,
            name=trimmed_name,
            hermes_home_path="",
            workspace_key="",
        )
        self._session.add(agent)
        self._session.flush()

        home_path = self._homes.build_home_path(user_id=user_id, agent_id=agent.id)
        agent.hermes_home_path = str(home_path)
        agent.workspace_key = f"agent:{agent.id}"
        self._homes.provision(home_path=home_path, agent_name=agent.name)
        self._session.add(agent)
        self._session.flush()
        return agent


class EnsureUserAgentService:
    def __init__(self, session: Session, settings: Settings):
        self._session = session
        self._creator = CreateAgentService(session, settings)

    def ensure_initial_agent(self, user: User) -> None:
        self._session.exec(
            select(User).where(User.id == user.id).with_for_update()
        ).one()
        existing = self._session.exec(
            select(Agent.id).where(Agent.user_id == user.id).limit(1)
        ).first()
        if existing is not None:
            return
        self._creator.create(user_id=user.id, name="Agent")
