from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from agent_runtime.ai.types import AssistantMessage, Message, ToolResultMessage, UserMessage
from agent_runtime.db import Agent, AgentSession, User, new_id


class AgentStore:
    def __init__(self, sessions: async_sessionmaker):
        self.sessions = sessions

    async def create_session(
        self,
        *,
        user_id: str,
        system_prompt: str,
        model: dict[str, Any],
        tenant_id: str = "default",
    ) -> AgentSession:
        async with self.sessions() as db:
            user = await db.get(User, user_id)
            if user is None:
                user = User(id=user_id)
                db.add(user)

            agent = Agent(
                id=new_id("agent"),
                user_id=user_id,
                system_prompt=system_prompt,
                model=model,
            )
            db.add(agent)
            await db.flush()

            session = AgentSession(
                id=new_id("sess"),
                user_id=user_id,
                agent_id=agent.id,
                tenant_id=tenant_id,
                messages=[],
            )
            db.add(session)
            await db.commit()
            return session

    async def get_session(
        self, *, session_id: str, user_id: str, tenant_id: str = "default"
    ) -> AgentSession | None:
        async with self.sessions() as db:
            result = await db.execute(
                select(AgentSession).where(
                    AgentSession.id == session_id,
                    AgentSession.user_id == user_id,
                    AgentSession.tenant_id == tenant_id,
                )
            )
            return result.scalar_one_or_none()

    async def get_agent(self, *, agent_id: str, user_id: str) -> Agent | None:
        async with self.sessions() as db:
            result = await db.execute(
                select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
            )
            return result.scalar_one_or_none()

    async def get_messages(
        self, *, session_id: str, user_id: str, tenant_id: str = "default"
    ) -> list[Message]:
        session = await self.get_session(session_id=session_id, user_id=user_id, tenant_id=tenant_id)
        if session is None:
            return []
        return [self._message_from_payload(payload) for payload in session.messages]

    async def save_messages(
        self,
        *,
        session_id: str,
        user_id: str,
        messages: list[Message],
        tenant_id: str = "default",
    ) -> None:
        async with self.sessions() as db:
            result = await db.execute(
                select(AgentSession).where(
                    AgentSession.id == session_id,
                    AgentSession.user_id == user_id,
                    AgentSession.tenant_id == tenant_id,
                )
            )
            session = result.scalar_one()
            session.messages = [message.model_dump(mode="json") for message in messages]
            await db.commit()

    async def delete_session(
        self, *, session_id: str, user_id: str, tenant_id: str = "default"
    ) -> None:
        async with self.sessions() as db:
            result = await db.execute(
                select(AgentSession).where(
                    AgentSession.id == session_id,
                    AgentSession.user_id == user_id,
                    AgentSession.tenant_id == tenant_id,
                )
            )
            session = result.scalar_one_or_none()
            if session is None:
                return
            agent_id = session.agent_id
            await db.execute(
                delete(AgentSession).where(
                    AgentSession.id == session_id,
                    AgentSession.user_id == user_id,
                    AgentSession.tenant_id == tenant_id,
                )
            )
            await db.execute(delete(Agent).where(Agent.id == agent_id, Agent.user_id == user_id))
            await db.commit()

    def _message_from_payload(self, payload: dict[str, Any]) -> Message:
        role = payload.get("role")
        if role == "user":
            return UserMessage.model_validate(payload)
        if role == "assistant":
            return AssistantMessage.model_validate(payload)
        if role == "toolResult":
            return ToolResultMessage.model_validate(payload)
        raise ValueError(f"Unsupported message role: {role}")
