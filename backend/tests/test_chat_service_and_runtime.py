from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from uuid import uuid4

from sqlmodel import Session

from app.hermes.manager import HermesRuntimeManager, HermesRuntimeSpec
from app.models.models import Agent, User
from app.services.chat import ChatService


class _FakeSessionDB:
    def __init__(self):
        self.history_by_session: dict[str, list[dict]] = {}
        self.closed = False

    def get_messages_as_conversation(self, session_id: str) -> list[dict]:
        return list(self.history_by_session.get(session_id, []))

    def close(self) -> None:
        self.closed = True


class _FakeAgent:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls: list[dict] = []

    def run_conversation(self, *, user_message: str, conversation_history=None, persist_user_message=None):
        self.calls.append(
            {
                "user_message": user_message,
                "conversation_history": list(conversation_history or []),
                "persist_user_message": persist_user_message,
            }
        )
        return {"final_response": f"echo:{user_message}"}


def test_runtime_manager_reuses_cached_agent_for_same_spec() -> None:
    built_agents: list[_FakeAgent] = []
    built_dbs: list[_FakeSessionDB] = []

    def _agent_factory(**kwargs):
        agent = _FakeAgent(**kwargs)
        built_agents.append(agent)
        return agent

    def _db_factory():
        db = _FakeSessionDB()
        built_dbs.append(db)
        return db

    manager = HermesRuntimeManager(
        ai_agent_factory=_agent_factory,
        session_db_factory=_db_factory,
        runtime_activator=lambda _spec: nullcontext(),
    )
    spec = HermesRuntimeSpec(
        agent_id=uuid4(),
        session_id="thread-1",
        hermes_home_path="/tmp/hermes/a",
        user_id="user-1",
        env={"OPENROUTER_API_KEY": "k1"},
    )

    first = manager.run_turn(spec=spec, user_message="hello")
    second = manager.run_turn(spec=spec, user_message="again")

    assert first["final_response"] == "echo:hello"
    assert second["final_response"] == "echo:again"
    assert len(built_agents) == 1
    assert len(built_dbs) == 1
    assert built_agents[0].calls[0]["conversation_history"] == []
    assert built_agents[0].calls[1]["persist_user_message"] == "again"

    manager.close()
    assert built_dbs[0].closed is True


def test_runtime_manager_rebuilds_cached_agent_when_env_changes() -> None:
    built_agents: list[_FakeAgent] = []

    manager = HermesRuntimeManager(
        ai_agent_factory=lambda **kwargs: built_agents.append(_FakeAgent(**kwargs)) or built_agents[-1],
        session_db_factory=_FakeSessionDB,
        runtime_activator=lambda _spec: nullcontext(),
    )
    base_spec = HermesRuntimeSpec(
        agent_id=uuid4(),
        session_id="thread-1",
        hermes_home_path="/tmp/hermes/a",
        user_id="user-1",
        env={"OPENROUTER_API_KEY": "k1"},
    )
    changed_env_spec = replace(base_spec, env={"OPENROUTER_API_KEY": "k2"})

    manager.run_turn(spec=base_spec, user_message="first")
    manager.run_turn(spec=changed_env_spec, user_message="second")

    assert len(built_agents) == 2
    manager.close()


class _FakeRuntimeManager:
    def __init__(self):
        self.calls: list[dict] = []

    def run_turn(self, *, spec: HermesRuntimeSpec, user_message: str, persist_user_message: str | None = None):
        self.calls.append(
            {
                "spec": spec,
                "user_message": user_message,
                "persist_user_message": persist_user_message,
            }
        )
        return {"final_response": "assistant reply"}


def test_chat_service_create_thread_and_send_message(db_session: Session) -> None:
    user = User(firebase_uid="uid-chat-1", email="chat1@example.com", name="Chat One")
    db_session.add(user)
    db_session.flush()
    agent = Agent(
        user_id=user.id,
        name="Primary",
        hermes_home_path="/tmp/hermes/home-1",
        workspace_key=f"agent:{uuid4()}",
    )
    db_session.add(agent)
    db_session.flush()

    runtime_manager = _FakeRuntimeManager()
    service = ChatService(db_session, runtime_manager=runtime_manager)

    thread = service.create_thread(user_id=user.id, agent_id=agent.id, title="  Planning  ")
    result = service.send_message(
        user_id=user.id,
        thread_id=thread.id,
        message="  Hello Hermes  ",
        runtime_env={"OPENROUTER_API_KEY": "test-key"},
    )

    assert thread.title == "Planning"
    assert thread.hermes_session_id
    assert thread.last_message_at is not None
    assert result.thread_id == thread.id
    assert result.session_id == thread.hermes_session_id
    assert result.response_text == "assistant reply"

    assert len(runtime_manager.calls) == 1
    call = runtime_manager.calls[0]
    assert call["user_message"] == "Hello Hermes"
    assert call["persist_user_message"] == "Hello Hermes"
    assert call["spec"].session_id == thread.hermes_session_id
    assert call["spec"].env["OPENROUTER_API_KEY"] == "test-key"


def test_chat_service_send_message_rejects_empty_message(db_session: Session) -> None:
    user = User(firebase_uid="uid-chat-2", email="chat2@example.com")
    db_session.add(user)
    db_session.flush()
    agent = Agent(
        user_id=user.id,
        name="Primary",
        hermes_home_path="/tmp/hermes/home-2",
        workspace_key=f"agent:{uuid4()}",
    )
    db_session.add(agent)
    db_session.flush()

    service = ChatService(db_session, runtime_manager=_FakeRuntimeManager())
    thread = service.create_thread(user_id=user.id, agent_id=agent.id)

    try:
        service.send_message(
            user_id=user.id,
            thread_id=thread.id,
            message="   ",
            runtime_env={"OPENROUTER_API_KEY": "test-key"},
        )
        assert False, "Expected ValueError for empty message"
    except ValueError as exc:
        assert str(exc) == "Message cannot be empty"

