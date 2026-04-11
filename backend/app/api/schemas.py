"""Response and request schemas for the backend API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.models.models import Agent, User


class AgentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AgentResponse(BaseModel):
    id: UUID
    name: str
    hermes_home_path: str
    workspace_key: str

    @classmethod
    def from_model(cls, agent: Agent) -> "AgentResponse":
        return cls(
            id=agent.id,
            name=agent.name,
            hermes_home_path=agent.hermes_home_path,
            workspace_key=agent.workspace_key,
        )


class UserResponse(BaseModel):
    id: UUID
    firebase_uid: str
    email: str
    name: str | None

    @classmethod
    def from_model(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            firebase_uid=user.firebase_uid,
            email=user.email,
            name=user.name,
        )


class MeResponse(BaseModel):
    user: UserResponse
    agents: list[AgentResponse]
