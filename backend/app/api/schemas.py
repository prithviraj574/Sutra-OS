"""Response and request schemas for the backend API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.models import Agent, ChatThread, User


class AgentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AuthExchangeRequest(BaseModel):
    id_token: str = Field(min_length=1)


class ChatThreadCreateRequest(BaseModel):
    agent_id: UUID
    title: str | None = Field(default=None, max_length=160)


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    runtime_env: dict[str, str] = Field(default_factory=dict)
    model: str = ""
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    user_home_path: str | None = None


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


class ChatThreadResponse(BaseModel):
    id: UUID
    user_id: UUID
    agent_id: UUID
    title: str
    hermes_session_id: str
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, thread: ChatThread) -> "ChatThreadResponse":
        return cls(
            id=thread.id,
            user_id=thread.user_id,
            agent_id=thread.agent_id,
            title=thread.title,
            hermes_session_id=thread.hermes_session_id,
            last_message_at=thread.last_message_at,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
        )


class ChatMessageResponse(BaseModel):
    thread_id: UUID
    session_id: str
    response_text: str
    raw_result: dict


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str | None

    @classmethod
    def from_model(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
        )


class MeResponse(BaseModel):
    user: UserResponse
    agents: list[AgentResponse]


class AuthExchangeResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    agents: list[AgentResponse]
