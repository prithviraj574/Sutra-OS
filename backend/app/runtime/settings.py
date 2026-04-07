import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeSettings:
    host_base_url: str
    api_key: str
    host_instance_name: str

    @classmethod
    def from_env(cls) -> "RuntimeSettings":
        base_url = os.getenv("GCP_RUNTIME_HOST_API_OVERRIDE_BASE_URL", "http://127.0.0.1:8787")
        api_key = os.getenv("SUTRA_RUNTIME_API_KEY", "")
        host_instance_name = os.getenv("GCP_RUNTIME_HOST_INSTANCE_NAME", "sutra-firecracker-host")
        return cls(
            host_base_url=base_url.rstrip("/"),
            api_key=api_key,
            host_instance_name=host_instance_name,
        )
