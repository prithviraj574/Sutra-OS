from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app import create_app
from config import Config
from database import init_db


@pytest.mark.asyncio
async def test_fastapi_session_and_non_stream_run() -> None:
    user_id = f"test_user_api_{uuid.uuid4().hex}"
    app = create_app(Config())
    await init_db(app.state.engine)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        agent_response = await client.post(
            "/v1/agent/agents",
            json={"user_id": user_id, "name": "Research agent"},
        )
        assert agent_response.status_code == 200
        agent_payload = agent_response.json()
        agent_id = agent_payload["id"]

        agents = await client.get("/v1/agent/agents", params={"user_id": user_id})
        assert agents.status_code == 200
        assert agents.json()[0]["id"] == agent_id

        created = await client.post(
            f"/v1/agent/agents/{agent_id}/sessions",
            json={
                "user_id": user_id,
                "system_prompt": "Session scoped prompt",
                "model": {
                    "id": "faux-tool-model",
                    "name": "Faux",
                    "api": "faux",
                    "provider": "faux",
                },
            },
        )
        assert created.status_code == 200
        created_payload = created.json()
        session_id = created_payload["session_id"]
        assert created_payload["agent_id"] == agent_id

        sessions = await client.get(
            f"/v1/agent/agents/{agent_id}/sessions",
            params={"user_id": user_id},
        )
        assert sessions.status_code == 200
        assert sessions.json()[0]["id"] == session_id

        stored_session = await app.state.store.get_session(session_id=session_id, user_id=user_id)
        assert stored_session.system_prompt == "Session scoped prompt"
        assert stored_session.model["provider"] == "faux"
        assert stored_session.tools == []

        response = await client.post(
            f"/v1/agent/sessions/{session_id}/messages",
            json={"user_id": user_id, "content": "hello", "stream": False},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][-1]["role"] == "assistant"

        listed = await client.get(
            f"/v1/agent/sessions/{session_id}/messages", params={"user_id": user_id}
        )
        assert listed.status_code == 200
        assert len(listed.json()["messages"]) == len(payload["messages"])

    await app.state.store.delete_session(session_id=session_id, user_id=user_id)
    await app.state.engine.dispose()


@pytest.mark.asyncio
async def test_localhost_and_127_frontend_origins_are_allowed() -> None:
    app = create_app(Config())
    await init_db(app.state.engine)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            response = await client.options(
                "/v1/agent/agents",
                headers={
                    "origin": origin,
                    "access-control-request-method": "GET",
                },
            )
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin

    await app.state.engine.dispose()
