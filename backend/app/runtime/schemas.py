from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class HostAgentStatus(BaseModel):
    agent_id: str
    state: str
    pd_name: str | None = None
    host_instance_name: str | None = None
    firecracker_id: str | None = None
    guest_ip: str | None = None
    booted_at: datetime | None = None
    ready: bool = False
    last_error: str | None = None


class AgentRuntimeResponse(BaseModel):
    agent_id: UUID
    state: str
    pd_name: str | None = None
    host_instance_name: str | None = None
    firecracker_id: str | None = None
    guest_ip: str | None = None
    booted_at: datetime | None = None
    last_seen_at: datetime | None = None
    ready: bool = False
    last_error: str | None = None
