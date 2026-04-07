from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from app.models.enums import AgentRuntimeState
from app.models.models import Agent, AgentRuntime
from app.runtime.host_client import HostManagerClient
from app.runtime.schemas import AgentRuntimeResponse, HostAgentStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def disk_name_for_agent(agent_id: UUID) -> str:
    return f"agent-{agent_id}"


class RuntimeService:
    def __init__(
        self,
        session: Session,
        host_client: HostManagerClient,
        host_instance_name: str,
    ):
        self.session = session
        self.host_client = host_client
        self.host_instance_name = host_instance_name

    def _get_agent(self, agent_id: UUID) -> Agent:
        agent = self.session.get(Agent, agent_id)
        if agent is None:
            raise LookupError(f"Agent {agent_id} does not exist")
        return agent

    def _get_or_create_runtime(self, agent_id: UUID) -> AgentRuntime:
        statement = select(AgentRuntime).where(AgentRuntime.agent_id == agent_id)
        runtime = self.session.exec(statement).first()
        if runtime is not None:
            return runtime

        runtime = AgentRuntime(
            agent_id=agent_id,
            state=AgentRuntimeState.STOPPED.value,
            pd_name=disk_name_for_agent(agent_id),
            host_instance_name=self.host_instance_name,
        )
        self.session.add(runtime)
        self.session.commit()
        self.session.refresh(runtime)
        return runtime

    def _apply_host_status(
        self,
        runtime: AgentRuntime,
        status: HostAgentStatus,
    ) -> AgentRuntimeResponse:
        runtime.state = status.state
        runtime.pd_name = status.pd_name or runtime.pd_name or disk_name_for_agent(runtime.agent_id)
        runtime.host_instance_name = status.host_instance_name or self.host_instance_name
        runtime.firecracker_id = status.firecracker_id
        runtime.guest_ip = status.guest_ip
        runtime.booted_at = status.booted_at if status.state == AgentRuntimeState.RUNNING.value else None
        runtime.last_seen_at = utc_now()
        runtime.last_error = status.last_error
        runtime.updated_at = utc_now()
        self.session.add(runtime)
        self.session.commit()
        self.session.refresh(runtime)

        return AgentRuntimeResponse(
            agent_id=runtime.agent_id,
            state=runtime.state,
            pd_name=runtime.pd_name,
            host_instance_name=runtime.host_instance_name,
            firecracker_id=runtime.firecracker_id,
            guest_ip=runtime.guest_ip,
            booted_at=runtime.booted_at,
            last_seen_at=runtime.last_seen_at,
            ready=status.ready,
            last_error=runtime.last_error,
        )

    async def ensure_runtime(self, agent_id: UUID) -> AgentRuntimeResponse:
        self._get_agent(agent_id)
        runtime = self._get_or_create_runtime(agent_id)
        runtime.state = AgentRuntimeState.STARTING.value
        runtime.last_seen_at = utc_now()
        runtime.updated_at = utc_now()
        runtime.last_error = None
        self.session.add(runtime)
        self.session.commit()
        self.session.refresh(runtime)

        try:
            status = await self.host_client.ensure(str(agent_id))
        except Exception as exc:
            runtime.state = AgentRuntimeState.ERROR.value
            runtime.last_error = str(exc)
            runtime.last_seen_at = utc_now()
            runtime.updated_at = utc_now()
            self.session.add(runtime)
            self.session.commit()
            self.session.refresh(runtime)
            raise

        return self._apply_host_status(runtime, status)

    async def stop_runtime(self, agent_id: UUID) -> AgentRuntimeResponse:
        self._get_agent(agent_id)
        runtime = self._get_or_create_runtime(agent_id)

        try:
            status = await self.host_client.stop(str(agent_id))
        except Exception as exc:
            runtime.state = AgentRuntimeState.ERROR.value
            runtime.last_error = str(exc)
            runtime.last_seen_at = utc_now()
            runtime.updated_at = utc_now()
            self.session.add(runtime)
            self.session.commit()
            self.session.refresh(runtime)
            raise

        return self._apply_host_status(runtime, status)

    async def get_runtime_status(self, agent_id: UUID) -> AgentRuntimeResponse:
        self._get_agent(agent_id)
        runtime = self._get_or_create_runtime(agent_id)

        try:
            status = await self.host_client.status(str(agent_id))
        except Exception as exc:
            runtime.state = AgentRuntimeState.ERROR.value
            runtime.last_error = str(exc)
            runtime.last_seen_at = utc_now()
            runtime.updated_at = utc_now()
            self.session.add(runtime)
            self.session.commit()
            self.session.refresh(runtime)
            raise

        return self._apply_host_status(runtime, status)
