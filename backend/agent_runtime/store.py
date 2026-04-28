from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from agent_runtime.agent.types import AgentMessage, CustomAgentMessage
from agent_runtime.ai.types import AssistantMessage, ToolResultMessage, UserMessage
from database import new_id
from models import Agent, AgentSession, User


class AgentStore:
    def __init__(self, sessions: async_sessionmaker):
        self.sessions = sessions

    async def ensure_user(self, *, user_id: str) -> None:
        async with self.sessions() as db:
            user = await db.get(User, user_id)
            if user is None:
                user = User(id=user_id)
                db.add(user)
                await db.commit()

    async def create_agent(self, *, user_id: str, name: str = "Default agent") -> Agent:
        async with self.sessions() as db:
            user = await db.get(User, user_id)
            if user is None:
                user = User(id=user_id)
                db.add(user)
            agent = Agent(
                id=new_id("agent"),
                user_id=user_id,
                name=name,
            )
            db.add(agent)
            await db.commit()
            return agent

    async def list_agents(self, *, user_id: str) -> list[Agent]:
        async with self.sessions() as db:
            result = await db.execute(
                select(Agent)
                .where(Agent.user_id == user_id)
                .order_by(Agent.updated_at.desc(), Agent.created_at.desc())
            )
            return list(result.scalars().all())

    async def create_session(
        self,
        *,
        user_id: str,
        agent_id: str,
        system_prompt: str,
        model: dict[str, Any],
        tools: list[dict[str, Any]] | None = None,
    ) -> AgentSession | None:
        async with self.sessions() as db:
            agent = await db.get(Agent, agent_id)
            if agent is None or agent.user_id != user_id:
                return None
            session = AgentSession(
                id=new_id("sess"),
                user_id=user_id,
                agent_id=agent.id,
                system_prompt=system_prompt,
                model=model,
                tools=tools or [],
                messages=[],
            )
            db.add(session)
            await db.commit()
            return session

    async def list_sessions(self, *, user_id: str, agent_id: str) -> list[AgentSession]:
        async with self.sessions() as db:
            result = await db.execute(
                select(AgentSession)
                .where(
                    AgentSession.user_id == user_id,
                    AgentSession.agent_id == agent_id,
                )
                .order_by(AgentSession.updated_at.desc(), AgentSession.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_session(self, *, session_id: str, user_id: str) -> AgentSession | None:
        async with self.sessions() as db:
            result = await db.execute(
                select(AgentSession).where(
                    AgentSession.id == session_id,
                    AgentSession.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()

    async def get_agent(self, *, agent_id: str, user_id: str) -> Agent | None:
        async with self.sessions() as db:
            result = await db.execute(
                select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
            )
            return result.scalar_one_or_none()

    async def get_messages(self, *, session_id: str, user_id: str) -> list[AgentMessage]:
        session = await self.get_session(session_id=session_id, user_id=user_id)
        if session is None:
            return []
        return [self._message_from_payload(payload) for payload in session.messages]

    async def save_messages(
        self,
        *,
        session_id: str,
        user_id: str,
        messages: list[AgentMessage],
    ) -> None:
        async with self.sessions() as db:
            result = await db.execute(
                select(AgentSession).where(
                    AgentSession.id == session_id,
                    AgentSession.user_id == user_id,
                )
            )
            session = result.scalar_one()
            session.messages = [message.model_dump(mode="json") for message in messages]
            await db.commit()

    async def delete_session(self, *, session_id: str, user_id: str) -> None:
        async with self.sessions() as db:
            result = await db.execute(
                select(AgentSession).where(
                    AgentSession.id == session_id,
                    AgentSession.user_id == user_id,
                )
            )
            session = result.scalar_one_or_none()
            if session is None:
                return
            await db.execute(
                delete(AgentSession).where(
                    AgentSession.id == session_id,
                    AgentSession.user_id == user_id,
                )
            )
            await db.commit()

    def _message_from_payload(self, payload: dict[str, Any]) -> AgentMessage:
        role = payload.get("role")
        if role == "user":
            return UserMessage.model_validate(payload)
        if role == "assistant":
            return AssistantMessage.model_validate(payload)
        if role == "toolResult":
            return ToolResultMessage.model_validate(payload)
        return CustomAgentMessage.model_validate(payload)
