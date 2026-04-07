import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HostRuntimeConfig:
    project_id: str
    zone: str
    host_instance_name: str
    api_key: str
    base_rootfs_path: str
    kernel_path: str
    firecracker_binary: str
    jailer_binary: str
    agents_dir: Path
    fc_uid: int
    fc_gid: int
    vcpu_count: int
    mem_size_mib: int
    disk_size_gb: int
    disk_type: str
    device_wait_timeout_s: int
    guest_api_port: int

    @classmethod
    def from_env(cls) -> "HostRuntimeConfig":
        return cls(
            project_id=os.environ.get("GCP_PROJECT_ID", ""),
            zone=os.environ.get("GCP_COMPUTE_ZONE", ""),
            host_instance_name=os.environ.get("GCP_RUNTIME_HOST_INSTANCE_NAME", "sutra-firecracker-host"),
            api_key=os.environ.get("SUTRA_RUNTIME_API_KEY", ""),
            base_rootfs_path=os.environ.get("BASE_ROOTFS_PATH", "/opt/sutra/base-rootfs.ext4"),
            kernel_path=os.environ.get("KERNEL_PATH", "/opt/sutra/vmlinux"),
            firecracker_binary=os.environ.get("FC_BINARY", "/usr/local/bin/firecracker"),
            jailer_binary=os.environ.get("JAILER_BINARY", "/usr/local/bin/jailer"),
            agents_dir=Path(os.environ.get("AGENTS_DIR", "/var/agents")),
            fc_uid=int(os.environ.get("FC_UID", "10000")),
            fc_gid=int(os.environ.get("FC_GID", "10000")),
            vcpu_count=int(os.environ.get("VCPU_COUNT", "1")),
            mem_size_mib=int(os.environ.get("MEM_SIZE_MIB", "512")),
            disk_size_gb=int(os.environ.get("AGENT_DISK_SIZE_GB", "20")),
            disk_type=os.environ.get("AGENT_DISK_TYPE", "pd-balanced"),
            device_wait_timeout_s=int(os.environ.get("DEVICE_WAIT_TIMEOUT_S", "60")),
            guest_api_port=int(os.environ.get("GUEST_API_PORT", "8642")),
        )
