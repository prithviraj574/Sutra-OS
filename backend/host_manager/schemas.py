from datetime import datetime

from pydantic import BaseModel


class HostAgentResponse(BaseModel):
    agent_id: str
    state: str
    pd_name: str
    host_instance_name: str
    firecracker_id: str | None = None
    guest_ip: str | None = None
    booted_at: datetime | None = None
    ready: bool = False
    last_error: str | None = None
