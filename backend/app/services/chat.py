"""Chat thread lifecycle and message execution services."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID, uuid4

from sqlmodel import Session, select

from app.hermes.manager import HermesRuntimeManager, HermesRuntimeSpec
from app.models.models import Agent, ChatThread


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def get_runtime_manager() -> HermesRuntimeManager:
    return HermesRuntimeManager()


@dataclass(frozen=True)
class ChatSendResult:
    thread_id: UUID
    session_id: str
    response_text: str
    raw_result: dict


class ChatService:
    def __init__(self, session: Session, runtime_manager: HermesRuntimeManager | None = None):
        self._session = session
        self._runtime_manager = runtime_manager or get_runtime_manager()

    def create_thread(
        self,
        *,
        user_id: UUID,
        agent_id: UUID,
        title: str | None = None,
    ) -> ChatThread:
        agent = self._session.exec(
            select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
        ).one_or_none()
        if agent is None:
            raise ValueError("Agent not found")

        normalized_title = (title or "").strip() or "New Chat"
        thread = ChatThread(
            user_id=user_id,
            agent_id=agent.id,
            title=normalized_title,
            hermes_session_id=uuid4().hex,
        )
        self._session.add(thread)
        self._session.flush()
        return thread

    def send_message(
        self,
        *,
        user_id: UUID,
        thread_id: UUID,
        message: str,
        runtime_env: Mapping[str, str],
        model: str = "",
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        user_home_path: str | None = None,
    ) -> ChatSendResult:
        text = message.strip()
        if not text:
            raise ValueError("Message cannot be empty")

        thread = self._session.exec(
            select(ChatThread).where(ChatThread.id == thread_id, ChatThread.user_id == user_id)
        ).one_or_none()
        if thread is None:
            raise ValueError("Thread not found")

        agent = self._session.exec(
            select(Agent).where(Agent.id == thread.agent_id, Agent.user_id == user_id)
        ).one_or_none()
        if agent is None:
            raise ValueError("Thread agent not found")

        spec = HermesRuntimeSpec(
            agent_id=agent.id,
            session_id=thread.hermes_session_id,
            hermes_home_path=agent.hermes_home_path,
            user_id=str(user_id),
            env=dict(runtime_env),
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            user_home_path=user_home_path,
        )
        raw_result = self._runtime_manager.run_turn(
            spec=spec,
            user_message=text,
            persist_user_message=text,
        )

        now = _utc_now()
        thread.last_message_at = now
        thread.updated_at = now
        if thread.title == "New Chat":
            thread.title = text[:80]
        self._session.add(thread)
        self._session.flush()

        response_text = str((raw_result or {}).get("final_response") or "")
        return ChatSendResult(
            thread_id=thread.id,
            session_id=thread.hermes_session_id,
            response_text=response_text,
            raw_result=raw_result,
        )

