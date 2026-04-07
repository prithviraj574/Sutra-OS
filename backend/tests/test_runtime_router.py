from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.runtime.router import get_runtime_service
from app.runtime.schemas import AgentRuntimeResponse


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FakeRuntimeService:
    async def ensure_runtime(self, agent_id):
        return AgentRuntimeResponse(
            agent_id=agent_id,
            state="running",
            pd_name=f"agent-{agent_id}",
            host_instance_name="sutra-firecracker-host",
            firecracker_id=str(agent_id),
            guest_ip="169.254.10.2",
            booted_at=utc_now(),
            last_seen_at=utc_now(),
            ready=True,
        )

    async def stop_runtime(self, agent_id):
        return AgentRuntimeResponse(
            agent_id=agent_id,
            state="stopped",
            pd_name=f"agent-{agent_id}",
            host_instance_name="sutra-firecracker-host",
            ready=False,
        )

    async def get_runtime_status(self, agent_id):
        return AgentRuntimeResponse(
            agent_id=agent_id,
            state="running",
            pd_name=f"agent-{agent_id}",
            host_instance_name="sutra-firecracker-host",
            ready=True,
        )


def test_ensure_runtime_endpoint_returns_runtime_payload():
    agent_id = uuid4()
    app.dependency_overrides[get_runtime_service] = lambda: FakeRuntimeService()

    with TestClient(app) as client:
        response = client.post(f"/internal/agents/{agent_id}/runtime/ensure")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_id"] == str(agent_id)
    assert payload["state"] == "running"
    assert payload["pd_name"] == f"agent-{agent_id}"
