from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.auth import issue_access_token
from app.models.models import Agent, ChatThread, User


class _FakeRuntimeManager:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run_turn(self, *, spec, user_message: str, persist_user_message: str | None = None):
        self.calls.append(
            {
                "spec": spec,
                "user_message": user_message,
                "persist_user_message": persist_user_message,
            }
        )
        return {"final_response": "assistant reply"}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user_and_agent(db_session: Session) -> tuple[User, Agent]:
    user = User(firebase_uid=f"uid-{uuid4()}", email=f"{uuid4().hex[:8]}@example.com", name="Chat User")
    db_session.add(user)
    db_session.flush()
    agent = Agent(
        user_id=user.id,
        name="Primary",
        hermes_home_path=f"/tmp/hermes/{uuid4()}",
        workspace_key=f"agent:{uuid4()}",
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(agent)
    return user, agent


def test_list_threads_returns_user_threads_only(
    client: TestClient,
    db_session: Session,
    settings,
) -> None:
    user, agent = _make_user_and_agent(db_session)
    other_user, other_agent = _make_user_and_agent(db_session)

    db_session.add(
        ChatThread(
            user_id=user.id,
            agent_id=agent.id,
            title="First",
            hermes_session_id="session-1",
        )
    )
    db_session.add(
        ChatThread(
            user_id=other_user.id,
            agent_id=other_agent.id,
            title="Other",
            hermes_session_id="session-2",
        )
    )
    db_session.commit()

    token, _ = issue_access_token(user, settings)
    response = client.get("/threads", headers=_bearer(token))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "First"


def test_create_thread_creates_new_chat_thread(
    client: TestClient,
    db_session: Session,
    settings,
) -> None:
    user, agent = _make_user_and_agent(db_session)
    token, _ = issue_access_token(user, settings)

    response = client.post(
        "/threads",
        headers=_bearer(token),
        json={"agent_id": str(agent.id), "title": "  Planning  "},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["agent_id"] == str(agent.id)
    assert payload["title"] == "Planning"
    assert payload["hermes_session_id"]


def test_create_thread_rejects_missing_agent(
    client: TestClient,
    db_session: Session,
    settings,
) -> None:
    user, _ = _make_user_and_agent(db_session)
    token, _ = issue_access_token(user, settings)

    response = client.post(
        "/threads",
        headers=_bearer(token),
        json={"agent_id": str(uuid4()), "title": "Missing"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


def test_send_message_uses_chat_service_runtime_manager(
    client: TestClient,
    db_session: Session,
    settings,
    monkeypatch,
) -> None:
    user, agent = _make_user_and_agent(db_session)
    thread = ChatThread(
        user_id=user.id,
        agent_id=agent.id,
        title="New Chat",
        hermes_session_id="thread-session-1",
    )
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    fake_runtime = _FakeRuntimeManager()
    monkeypatch.setattr("app.services.chat.get_runtime_manager", lambda: fake_runtime)

    token, _ = issue_access_token(user, settings)
    response = client.post(
        f"/threads/{thread.id}/messages",
        headers=_bearer(token),
        json={
            "message": "  Hello Hermes  ",
            "runtime_env": {"OPENROUTER_API_KEY": "test-key"},
            "provider": "openrouter",
            "model": "anthropic/claude-sonnet-4",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["thread_id"] == str(thread.id)
    assert payload["session_id"] == "thread-session-1"
    assert payload["response_text"] == "assistant reply"

    assert len(fake_runtime.calls) == 1
    call = fake_runtime.calls[0]
    assert call["user_message"] == "Hello Hermes"
    assert call["persist_user_message"] == "Hello Hermes"
    assert call["spec"].provider == "openrouter"
    assert call["spec"].model == "anthropic/claude-sonnet-4"
    assert call["spec"].env["OPENROUTER_API_KEY"] == "test-key"


def test_send_message_returns_404_for_missing_thread(
    client: TestClient,
    db_session: Session,
    settings,
    monkeypatch,
) -> None:
    user, _ = _make_user_and_agent(db_session)
    monkeypatch.setattr("app.services.chat.get_runtime_manager", lambda: _FakeRuntimeManager())
    token, _ = issue_access_token(user, settings)

    response = client.post(
        f"/threads/{uuid4()}/messages",
        headers=_bearer(token),
        json={"message": "hello"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Thread not found"


def test_send_message_rejects_empty_message(
    client: TestClient,
    db_session: Session,
    settings,
    monkeypatch,
) -> None:
    user, agent = _make_user_and_agent(db_session)
    thread = ChatThread(
        user_id=user.id,
        agent_id=agent.id,
        title="Chat",
        hermes_session_id="thread-session-2",
    )
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)

    monkeypatch.setattr("app.services.chat.get_runtime_manager", lambda: _FakeRuntimeManager())
    token, _ = issue_access_token(user, settings)

    response = client.post(
        f"/threads/{thread.id}/messages",
        headers=_bearer(token),
        json={"message": "   "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Message cannot be empty"
