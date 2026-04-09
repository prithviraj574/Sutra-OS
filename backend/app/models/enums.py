from enum import StrEnum


class AgentSandboxState(StrEnum):
    STOPPED = "stopped"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    FAILED = "failed"
