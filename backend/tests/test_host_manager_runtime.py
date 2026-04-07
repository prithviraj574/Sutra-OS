import asyncio
from datetime import datetime, timezone
from pathlib import Path

from host_manager.config import HostRuntimeConfig
from host_manager.firecracker import FirecrackerManager, RunningVM
from host_manager.gcp_disk import GCPPersistentDiskManager


def make_config(tmp_path: Path) -> HostRuntimeConfig:
    return HostRuntimeConfig(
        project_id="project-1",
        zone="us-central1-a",
        host_instance_name="sutra-firecracker-host",
        api_key="secret",
        base_rootfs_path="/opt/sutra/base-rootfs.ext4",
        kernel_path="/opt/sutra/vmlinux",
        firecracker_binary="/usr/local/bin/firecracker",
        jailer_binary="/usr/local/bin/jailer",
        agents_dir=tmp_path,
        fc_uid=10000,
        fc_gid=10000,
        vcpu_count=1,
        mem_size_mib=512,
        disk_size_gb=20,
        disk_type="pd-balanced",
        device_wait_timeout_s=1,
        guest_api_port=8642,
    )


def test_status_recovers_running_vm_from_persisted_state(tmp_path: Path):
    manager = FirecrackerManager(make_config(tmp_path))
    agent_id = "123e4567-e89b-12d3-a456-426614174000"
    running_vm = RunningVM(
        agent_id=agent_id,
        pd_name=agent_id,
        pid=4242,
        firecracker_id=agent_id,
        guest_ip="169.254.10.2",
        host_ip="169.254.10.1",
        booted_at=datetime.now(timezone.utc),
    )
    manager._write_state(running_vm)
    manager.running_vms.clear()
    manager._pid_exists = lambda pid: pid == 4242  # type: ignore[method-assign]

    recovered = manager.status(agent_id)

    assert recovered is not None
    assert recovered.pid == 4242
    assert recovered.guest_ip == "169.254.10.2"


def test_status_cleans_up_stale_state(tmp_path: Path):
    manager = FirecrackerManager(make_config(tmp_path))
    agent_id = "123e4567-e89b-12d3-a456-426614174001"
    running_vm = RunningVM(
        agent_id=agent_id,
        pd_name=agent_id,
        pid=5252,
        firecracker_id=agent_id,
        guest_ip="169.254.11.2",
        host_ip="169.254.11.1",
        booted_at=datetime.now(timezone.utc),
    )
    manager._write_state(running_vm)
    calls: list[tuple[str, str]] = []
    manager._pid_exists = lambda pid: False  # type: ignore[method-assign]
    manager.teardown_tap = lambda aid, gip: calls.append((aid, gip))  # type: ignore[method-assign]

    recovered = manager.status(agent_id)

    assert recovered is None
    assert calls == [(agent_id, "169.254.11.2")]
    assert not manager.state_path(agent_id).exists()


def test_wait_for_device_returns_when_present(tmp_path: Path):
    manager = GCPPersistentDiskManager(
        project_id="project-1",
        zone="us-central1-a",
        host_instance_name="sutra-firecracker-host",
        device_wait_timeout_s=1,
    )
    disk_name = "disk-1"
    device_path = tmp_path / f"google-{disk_name}"
    manager.host_device_path = lambda _: str(device_path)  # type: ignore[method-assign]
    device_path.write_text("", encoding="utf-8")

    resolved = asyncio.run(manager.wait_for_device(disk_name))

    assert resolved == str(device_path)


def test_firecracker_uses_jail_local_paths(tmp_path: Path):
    manager = FirecrackerManager(make_config(tmp_path))
    agent_id = "123e4567-e89b-12d3-a456-426614174002"
    firecracker_id = manager.firecracker_id(agent_id)

    assert manager.socket_path(agent_id).endswith(
        f"/{agent_id}/firecracker/{firecracker_id}/root/run/firecracker.socket"
    )
    assert len(firecracker_id) == 12
    assert manager.api_socket_path() == "/run/firecracker.socket"
    assert manager.jailed_path("rootfs.ext4") == "/rootfs.ext4"
