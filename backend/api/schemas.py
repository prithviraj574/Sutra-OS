from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent_runtime.ai.types import Message


class SessionCreate(BaseModel):
    user_id: str
    system_prompt: str | None = None
    model: dict[str, Any] | None = None


class SessionCreated(BaseModel):
    session_id: str
    user_id: str


class UserInput(BaseModel):
    user_id: str
    content: str
    stream: bool = True


class MessagesResponse(BaseModel):
    session_id: str
    messages: list[Message] = Field(default_factory=list)
