from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.ai.types import Message


class AgentCreate(BaseModel):
    user_id: str
    name: str = "Default agent"


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    created_at: datetime
    updated_at: datetime


class SessionCreate(BaseModel):
    user_id: str
    system_prompt: str | None = None
    model: dict[str, Any] | None = None


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    agent_id: str
    status: str
    created_at: datetime
    updated_at: datetime


class SessionCreated(BaseModel):
    session_id: str
    agent_id: str
    user_id: str


class UserInput(BaseModel):
    user_id: str
    content: str
    stream: bool = True


class MessagesResponse(BaseModel):
    session_id: str
    messages: list[Message] = Field(default_factory=list)
