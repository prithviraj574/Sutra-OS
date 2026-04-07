import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.models import Agent, AgentRuntime, User
from app.runtime.schemas import HostAgentStatus
from app.runtime.service import RuntimeService, disk_name_for_agent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FakeHostManagerClient:
    async def ensure(self, agent_id: str) -> HostAgentStatus:
        return HostAgentStatus(
            agent_id=agent_id,
            state="running",
            pd_name=f"agent-{agent_id}",
            host_instance_name="sutra-firecracker-host",
            firecracker_id=agent_id,
            guest_ip="169.254.10.2",
            booted_at=utc_now(),
            ready=True,
        )

    async def stop(self, agent_id: str) -> HostAgentStatus:
        return HostAgentStatus(
            agent_id=agent_id,
            state="stopped",
            pd_name=f"agent-{agent_id}",
            host_instance_name="sutra-firecracker-host",
            ready=False,
        )

    async def status(self, agent_id: str) -> HostAgentStatus:
        return HostAgentStatus(
            agent_id=agent_id,
            state="running",
            pd_name=f"agent-{agent_id}",
            host_instance_name="sutra-firecracker-host",
            firecracker_id=agent_id,
            guest_ip="169.254.10.2",
            booted_at=utc_now(),
            ready=True,
        )


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def seed_agent(session: Session) -> Agent:
    user = User(firebase_uid="firebase-1", email="user@example.com", name="User")
    session.add(user)
    session.commit()
    session.refresh(user)

    agent = Agent(user_id=user.id, name="Agent 1")
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def test_ensure_runtime_creates_runtime_row():
    session = make_session()
    agent = seed_agent(session)
    service = RuntimeService(session, FakeHostManagerClient(), "sutra-firecracker-host")

    response = asyncio.run(service.ensure_runtime(agent.id))

    assert response.state == "running"
    assert response.ready is True
    assert response.pd_name == disk_name_for_agent(agent.id)

    stored_runtime = session.exec(
        select(AgentRuntime).where(AgentRuntime.agent_id == agent.id)
    ).first()
    assert stored_runtime is not None
    assert stored_runtime.state == "running"
    assert stored_runtime.pd_name == disk_name_for_agent(agent.id)


def test_stop_runtime_marks_agent_stopped():
    session = make_session()
    agent = seed_agent(session)
    service = RuntimeService(session, FakeHostManagerClient(), "sutra-firecracker-host")

    asyncio.run(service.ensure_runtime(agent.id))
    response = asyncio.run(service.stop_runtime(agent.id))

    stored_runtime = session.exec(
        select(AgentRuntime).where(AgentRuntime.agent_id == agent.id)
    ).first()
    assert response.state == "stopped"
    assert response.ready is False
    assert stored_runtime is not None
    assert stored_runtime.state == "stopped"


def test_runtime_status_raises_for_unknown_agent():
    session = make_session()
    service = RuntimeService(session, FakeHostManagerClient(), "sutra-firecracker-host")

    missing_agent_id = uuid4()

    try:
        asyncio.run(service.get_runtime_status(missing_agent_id))
    except LookupError as exc:
        assert str(missing_agent_id) in str(exc)
    else:
        raise AssertionError("Expected LookupError for missing agent")
