from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from agent_runtime.ai.types import AssistantMessage, Message, ToolResultMessage, UserMessage
from agent_runtime.db import AgentEventRecord, AgentMessageRecord, AgentSessionRecord, new_id


class AgentRepository:
    def __init__(self, sessions: async_sessionmaker):
        self.sessions = sessions

    async def create_session(
        self,
        *,
        user_id: str,
        system_prompt: str,
        model: dict[str, Any],
        tenant_id: str = "default",
    ) -> AgentSessionRecord:
        record = AgentSessionRecord(
            id=new_id("sess"),
            user_id=user_id,
            tenant_id=tenant_id,
            system_prompt=system_prompt,
            model=model,
        )
        async with self.sessions() as session:
            session.add(record)
            await session.commit()
        return record

    async def get_session(
        self, *, session_id: str, user_id: str, tenant_id: str = "default"
    ) -> AgentSessionRecord | None:
        async with self.sessions() as session:
            result = await session.execute(
                select(AgentSessionRecord).where(
                    AgentSessionRecord.id == session_id,
                    AgentSessionRecord.user_id == user_id,
                    AgentSessionRecord.tenant_id == tenant_id,
                )
            )
            return result.scalar_one_or_none()

    async def list_messages(
        self, *, session_id: str, user_id: str, tenant_id: str = "default"
    ) -> list[Message]:
        async with self.sessions() as session:
            result = await session.execute(
                select(AgentMessageRecord)
                .where(
                    AgentMessageRecord.session_id == session_id,
                    AgentMessageRecord.user_id == user_id,
                    AgentMessageRecord.tenant_id == tenant_id,
                )
                .order_by(AgentMessageRecord.created_at, AgentMessageRecord.id)
            )
            records = result.scalars().all()
        return [self._message_from_payload(record.payload) for record in records]

    async def append_messages(
        self,
        *,
        session_id: str,
        user_id: str,
        messages: Sequence[Message],
        tenant_id: str = "default",
    ) -> None:
        async with self.sessions() as session:
            for message in messages:
                session.add(
                    AgentMessageRecord(
                        id=new_id("msg"),
                        session_id=session_id,
                        user_id=user_id,
                        tenant_id=tenant_id,
                        role=message.role,
                        payload=message.model_dump(mode="json"),
                    )
                )
            await session.commit()

    async def append_event(
        self,
        *,
        session_id: str,
        user_id: str,
        event_type: str,
        payload: dict[str, Any],
        tenant_id: str = "default",
    ) -> None:
        async with self.sessions() as session:
            session.add(
                AgentEventRecord(
                    id=new_id("evt"),
                    session_id=session_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    type=event_type,
                    payload=payload,
                )
            )
            await session.commit()

    async def delete_session(
        self, *, session_id: str, user_id: str, tenant_id: str = "default"
    ) -> None:
        async with self.sessions() as session:
            await session.execute(
                delete(AgentEventRecord).where(
                    AgentEventRecord.session_id == session_id,
                    AgentEventRecord.user_id == user_id,
                    AgentEventRecord.tenant_id == tenant_id,
                )
            )
            await session.execute(
                delete(AgentMessageRecord).where(
                    AgentMessageRecord.session_id == session_id,
                    AgentMessageRecord.user_id == user_id,
                    AgentMessageRecord.tenant_id == tenant_id,
                )
            )
            await session.execute(
                delete(AgentSessionRecord).where(
                    AgentSessionRecord.id == session_id,
                    AgentSessionRecord.user_id == user_id,
                    AgentSessionRecord.tenant_id == tenant_id,
                )
            )
            await session.commit()

    def _message_from_payload(self, payload: dict[str, Any]) -> Message:
        role = payload.get("role")
        if role == "user":
            return UserMessage.model_validate(payload)
        if role == "assistant":
            return AssistantMessage.model_validate(payload)
        if role == "toolResult":
            return ToolResultMessage.model_validate(payload)
        raise ValueError(f"Unsupported message role: {role}")
