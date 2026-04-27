from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app import create_app
from agent_runtime.db import init_db
from config import Config


@pytest.mark.asyncio
async def test_fastapi_session_and_non_stream_run() -> None:
    user_id = "test_user_api"
    app = create_app(Config())
    await init_db(app.state.engine)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/v1/agent/sessions", json={"user_id": user_id})
        assert created.status_code == 200
        session_id = created.json()["session_id"]

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
