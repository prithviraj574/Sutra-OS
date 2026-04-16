from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import jwt
from sqlmodel import Session, select

from app.core.auth import issue_access_token
from app.models.models import Agent, User


def _exchange(client: TestClient, id_token: str) -> dict:
    response = client.post("/auth/exchange", json={"id_token": id_token})
    assert response.status_code == 200, response.text
    return response.json()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_exchange_creates_user_and_initial_agent(
    client: TestClient,
    clean_state: dict,
) -> None:
    payload = _exchange(client, "uid-1|alice@example.com|Alice")

    assert payload["token_type"] == "bearer"
    assert payload["user"]["email"] == "alice@example.com"
    assert len(payload["agents"]) == 1

    agent = payload["agents"][0]
    assert agent["name"] == "Agent"
    assert agent["workspace_key"].startswith("agent:")
    assert str(clean_state["homes_root"]) in agent["hermes_home_path"]

    hermes_home = Path(agent["hermes_home_path"])
    assert (hermes_home / "SOUL.md").exists()
    assert (hermes_home / "memories" / "USER.md").exists()
    assert (hermes_home / "memories" / "MEMORY.md").exists()


def test_auth_exchange_same_uid_updates_user_without_duplicate_agent(
    client: TestClient,
    db_session: Session,
) -> None:
    _exchange(client, "uid-1|alice@example.com|Alice")
    second = _exchange(client, "uid-1|alice+new@example.com|Alice Updated")

    assert second["user"]["email"] == "alice+new@example.com"
    assert second["user"]["name"] == "Alice Updated"
    assert len(second["agents"]) == 1

    users = db_session.exec(select(User)).all()
    agents = db_session.exec(select(Agent)).all()
    assert len(users) == 1
    assert len(agents) == 1


def test_auth_exchange_accepts_jwt_like_dev_token(
    client: TestClient,
    db_session: Session,
) -> None:
    dev_jwt = jwt.encode(
        {
            "sub": "firebase-user-1",
            "email": "jwt-user@example.com",
            "name": "JWT User",
        },
        "dev-bypass-secret-at-least-32-chars",
        algorithm="HS256",
    )

    payload = _exchange(client, dev_jwt)

    assert payload["user"]["email"] == "jwt-user@example.com"
    assert payload["user"]["name"] == "JWT User"
    users = db_session.exec(select(User)).all()
    assert len(users) == 1
    assert users[0].firebase_uid == "firebase-user-1"


def test_me_bootstraps_initial_agent_when_missing(
    client: TestClient,
    db_session: Session,
    settings,
) -> None:
    user = User(
        firebase_uid="uid-direct",
        email="direct@example.com",
        name="Direct User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token, _ = issue_access_token(user, settings)
    response = client.get("/me", headers=_bearer(token))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user"]["id"] == str(user.id)
    assert len(payload["agents"]) == 1
    assert payload["agents"][0]["name"] == "Agent"


def test_agents_requires_valid_access_token(client: TestClient) -> None:
    missing = client.get("/agents")
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Missing Authorization header"

    invalid = client.get("/agents", headers=_bearer("not-a-real-token"))
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid access token"


def test_current_user_dependency_rejects_nonexistent_subject(
    client: TestClient,
    settings,
) -> None:
    phantom_user = User(
        id=uuid4(),
        firebase_uid="ghost-user",
        email="ghost@example.com",
    )
    token, _ = issue_access_token(phantom_user, settings)

    response = client.get("/agents", headers=_bearer(token))
    assert response.status_code == 401
    assert response.json()["detail"] == "User not found"


def test_create_agent_creates_second_agent_for_user(client: TestClient) -> None:
    exchange = _exchange(client, "uid-creator|creator@example.com|Creator")
    token = exchange["access_token"]

    response = client.post(
        "/agents",
        headers=_bearer(token),
        json={"name": "  Research  "},
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["name"] == "Research"
    assert created["workspace_key"].startswith("agent:")

    listing = client.get("/agents", headers=_bearer(token))
    assert listing.status_code == 200, listing.text
    names = [agent["name"] for agent in listing.json()]
    assert names == ["Agent", "Research"]


def test_create_agent_rejects_whitespace_only_name(client: TestClient) -> None:
    exchange = _exchange(client, "uid-creator|creator@example.com|Creator")
    token = exchange["access_token"]

    response = client.post(
        "/agents",
        headers=_bearer(token),
        json={"name": "   "},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Agent name cannot be empty"
