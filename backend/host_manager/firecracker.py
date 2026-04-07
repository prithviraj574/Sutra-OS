import asyncio
import hashlib
import json
import logging
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from host_manager.config import HostRuntimeConfig

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RunningVM:
    agent_id: str
    pd_name: str
    pid: int
    firecracker_id: str
    guest_ip: str
    host_ip: str
    booted_at: datetime


def _run(cmd: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    logger.info("$ %s", cmd)
    return subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)


class FirecrackerManager:
    def __init__(self, config: HostRuntimeConfig):
        self.config = config
        self.running_vms: dict[str, RunningVM] = {}
        self.config.agents_dir.mkdir(parents=True, exist_ok=True)

    def agent_dir(self, agent_id: str) -> Path:
        path = self.config.agents_dir / agent_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def jail_root(self, agent_id: str) -> Path:
        return self.agent_dir(agent_id) / "firecracker" / self.firecracker_id(agent_id) / "root"

    def socket_path(self, agent_id: str) -> str:
        return str(self.jail_root(agent_id) / "run" / "firecracker.socket")

    def api_socket_path(self) -> str:
        return "/run/firecracker.socket"

    def jailed_path(self, path: str) -> str:
        return f"/{path}"

    def state_path(self, agent_id: str) -> Path:
        return self.agent_dir(agent_id) / "runtime.json"

    def tap_name(self, agent_id: str) -> str:
        return f"fc-{agent_id[:8]}"

    def firecracker_id(self, agent_id: str) -> str:
        return hashlib.sha256(agent_id.encode("utf-8")).hexdigest()[:12]

    def _agent_hex(self, agent_id: str) -> str:
        return agent_id.replace("-", "")

    def _stable_slot(self, agent_id: str) -> int:
        digest = hashlib.sha256(agent_id.encode("utf-8")).digest()
        return (int.from_bytes(digest[:2], "big") % 16000) + 1

    def allocate_ip_pair(self, agent_id: str) -> tuple[str, str]:
        slot = self._stable_slot(agent_id)
        third_octet = slot // 64
        fourth_block = (slot % 64) * 4
        host_ip = f"169.254.{third_octet}.{fourth_block + 1}"
        guest_ip = f"169.254.{third_octet}.{fourth_block + 2}"
        return host_ip, guest_ip

    def _write_state(self, running_vm: RunningVM) -> None:
        self.state_path(running_vm.agent_id).write_text(
            json.dumps(
                {
                    "agent_id": running_vm.agent_id,
                    "pd_name": running_vm.pd_name,
                    "pid": running_vm.pid,
                    "firecracker_id": running_vm.firecracker_id,
                    "guest_ip": running_vm.guest_ip,
                    "host_ip": running_vm.host_ip,
                    "booted_at": running_vm.booted_at.isoformat(),
                }
            ),
            encoding="utf-8",
        )

    def _read_state(self, agent_id: str) -> RunningVM | None:
        state_path = self.state_path(agent_id)
        if not state_path.exists():
            return None

        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            return RunningVM(
                agent_id=payload["agent_id"],
                pd_name=payload["pd_name"],
                pid=int(payload["pid"]),
                firecracker_id=payload["firecracker_id"],
                guest_ip=payload["guest_ip"],
                host_ip=payload["host_ip"],
                booted_at=datetime.fromisoformat(payload["booted_at"]),
            )
        except (KeyError, ValueError, json.JSONDecodeError):
            logger.warning("Ignoring invalid runtime state for %s", agent_id)
            self._clear_state(agent_id)
            return None

    def _clear_state(self, agent_id: str) -> None:
        self.state_path(agent_id).unlink(missing_ok=True)

    def _pid_exists(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _wait_for_pid_exit(self, pid: int, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if not self._pid_exists(pid):
                return True
            time.sleep(0.1)
        return not self._pid_exists(pid)

    def ensure_disk_formatted(self, device_path: str) -> None:
        result = _run(f"blkid {device_path}", check=False)
        if result.returncode != 0 or "ext4" not in result.stdout:
            _run(f"mkfs.ext4 -F {device_path}")

    def _copy_into_jail(self, source: str, target: Path) -> None:
        source_path = Path(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_mtime_ns == source_path.stat().st_mtime_ns:
            return
        target.unlink(missing_ok=True)
        try:
            os.link(source_path, target)
        except OSError:
            shutil.copy2(source_path, target)

    def _prepare_workspace_device(self, workspace_device: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(exist_ok=True)
        real_device = os.path.realpath(workspace_device)
        _run(f"chown {self.config.fc_uid}:{self.config.fc_gid} {real_device}", check=False)
        mount_source = _run(f"findmnt -n -o SOURCE --target {target}", check=False).stdout.strip()
        if mount_source and mount_source != real_device:
            _run(f"umount {target}", check=False)
            mount_source = ""
        if not mount_source:
            _run(f"mount --bind {real_device} {target}")

    def _cleanup_workspace_device(self, agent_id: str) -> None:
        workspace_target = self.jail_root(agent_id) / "workspace.dev"
        if workspace_target.exists():
            _run(f"umount {workspace_target}", check=False)

    def stage_jailed_resources(self, agent_id: str, workspace_device: str) -> tuple[str, str, str]:
        jail_root = self.jail_root(agent_id)
        kernel_name = "vmlinux"
        rootfs_name = "rootfs.ext4"
        workspace_name = "workspace.dev"
        self._copy_into_jail(self.config.kernel_path, jail_root / kernel_name)
        self._copy_into_jail(self.config.base_rootfs_path, jail_root / rootfs_name)
        self._prepare_workspace_device(workspace_device, jail_root / workspace_name)
        return (
            self.jailed_path(kernel_name),
            self.jailed_path(rootfs_name),
            self.jailed_path(workspace_name),
        )

    def setup_tap(self, agent_id: str, host_ip: str, guest_ip: str) -> str:
        tap = self.tap_name(agent_id)
        _run(f"ip tuntap add {tap} mode tap", check=False)
        _run(f"ip addr add {host_ip}/30 dev {tap}", check=False)
        _run(f"ip link set {tap} up")
        host_iface = _run("ip route | awk '/default/ {print $5; exit}'").stdout.strip()
        if host_iface:
            _run(
                f"iptables -t nat -A POSTROUTING -s {guest_ip} -o {host_iface} -j MASQUERADE",
                check=False,
            )
        return tap

    def teardown_tap(self, agent_id: str, guest_ip: str) -> None:
        tap = self.tap_name(agent_id)
        host_iface = _run("ip route | awk '/default/ {print $5; exit}'", check=False).stdout.strip()
        if host_iface:
            _run(
                f"iptables -t nat -D POSTROUTING -s {guest_ip} -o {host_iface} -j MASQUERADE",
                check=False,
            )
        _run(f"ip link delete {tap}", check=False)

    async def _fc_request(self, agent_id: str, method: str, path: str, payload: dict) -> None:
        transport = httpx.AsyncHTTPTransport(uds=self.socket_path(agent_id))
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            response = await client.request(method, path, json=payload)
            response.raise_for_status()

    async def start(self, agent_id: str, pd_name: str, workspace_device: str) -> RunningVM:
        running_vm = self.status(agent_id)
        if running_vm is not None:
            return running_vm

        host_ip, guest_ip = self.allocate_ip_pair(agent_id)
        tap = self.setup_tap(agent_id, host_ip, guest_ip)
        agent_dir = self.agent_dir(agent_id)
        shutil.rmtree(agent_dir / "firecracker", ignore_errors=True)
        socket_path = self.socket_path(agent_id)

        cmd = [
            self.config.jailer_binary,
            "--id",
            self.firecracker_id(agent_id),
            "--uid",
            str(self.config.fc_uid),
            "--gid",
            str(self.config.fc_gid),
            "--exec-file",
            self.config.firecracker_binary,
            "--chroot-base-dir",
            str(agent_dir),
            "--",
            "--api-sock",
            self.api_socket_path(),
        ]
        log_path = agent_dir / "firecracker.log"
        with log_path.open("a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )

            for _ in range(50):
                if Path(socket_path).exists():
                    break
                await asyncio.sleep(0.1)
            else:
                process.kill()
                self.teardown_tap(agent_id, guest_ip)
                raise RuntimeError(f"Firecracker socket did not appear for {agent_id}")

        if process.poll() is not None:
            self.teardown_tap(agent_id, guest_ip)
            raise RuntimeError(f"Firecracker exited immediately for {agent_id}")

        try:
            kernel_path, rootfs_path, workspace_path = self.stage_jailed_resources(
                agent_id,
                workspace_device,
            )
            await self._fc_request(
                agent_id,
                "PUT",
                "/boot-source",
                {
                    "kernel_image_path": kernel_path,
                    "boot_args": (
                        "console=ttyS0 reboot=k panic=1 pci=off "
                        f"ip={guest_ip}::{host_ip}:255.255.255.252::eth0:off"
                    ),
                },
            )
            await self._fc_request(
                agent_id,
                "PUT",
                "/drives/rootfs",
                {
                    "drive_id": "rootfs",
                    "path_on_host": rootfs_path,
                    "is_root_device": True,
                    "is_read_only": True,
                },
            )
            await self._fc_request(
                agent_id,
                "PUT",
                "/drives/workspace",
                {
                    "drive_id": "workspace",
                    "path_on_host": workspace_path,
                    "is_root_device": False,
                    "is_read_only": False,
                },
            )
            await self._fc_request(
                agent_id,
                "PUT",
                "/network-interfaces/eth0",
                {
                    "iface_id": "eth0",
                    "guest_mac": (
                        f"02:FC:{self._agent_hex(agent_id)[:2]}:{self._agent_hex(agent_id)[2:4]}:"
                        f"{self._agent_hex(agent_id)[4:6]}:{self._agent_hex(agent_id)[6:8]}"
                    ),
                    "host_dev_name": tap,
                },
            )
            await self._fc_request(
                agent_id,
                "PUT",
                "/machine-config",
                {
                    "vcpu_count": self.config.vcpu_count,
                    "mem_size_mib": self.config.mem_size_mib,
                    "smt": False,
                },
            )
            await self._fc_request(
                agent_id,
                "PUT",
                "/actions",
                {"action_type": "InstanceStart"},
            )
        except Exception:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            self._cleanup_workspace_device(agent_id)
            self.teardown_tap(agent_id, guest_ip)
            self._clear_state(agent_id)
            raise

        running_vm = RunningVM(
            agent_id=agent_id,
            pd_name=pd_name,
            pid=process.pid,
            firecracker_id=self.firecracker_id(agent_id),
            guest_ip=guest_ip,
            host_ip=host_ip,
            booted_at=utc_now(),
        )
        self.running_vms[agent_id] = running_vm
        self._write_state(running_vm)
        return running_vm

    def _cleanup_stale_runtime(self, running_vm: RunningVM) -> None:
        self.running_vms.pop(running_vm.agent_id, None)
        self._cleanup_workspace_device(running_vm.agent_id)
        self.teardown_tap(running_vm.agent_id, running_vm.guest_ip)
        self._clear_state(running_vm.agent_id)

    def stop(self, agent_id: str) -> None:
        running_vm = self.status(agent_id)
        if running_vm is None:
            self._clear_state(agent_id)
            return

        try:
            os.kill(running_vm.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

        if not self._wait_for_pid_exit(running_vm.pid, timeout_s=5):
            try:
                os.kill(running_vm.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self._wait_for_pid_exit(running_vm.pid, timeout_s=2)

        self._cleanup_workspace_device(agent_id)
        self.teardown_tap(agent_id, running_vm.guest_ip)
        self.running_vms.pop(agent_id, None)
        self._clear_state(agent_id)

    async def is_ready(self, agent_id: str) -> bool:
        running_vm = self.status(agent_id)
        if running_vm is None:
            return False

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                for path in ("/health", "/v1/models"):
                    response = await client.get(
                        f"http://{running_vm.guest_ip}:{self.config.guest_api_port}{path}"
                    )
                    if response.status_code == 200:
                        return True
                return False
        except Exception:
            return False

    def status(self, agent_id: str) -> RunningVM | None:
        running_vm = self.running_vms.get(agent_id)
        if running_vm is None:
            running_vm = self._read_state(agent_id)
            if running_vm is None:
                return None
            self.running_vms[agent_id] = running_vm

        if not self._pid_exists(running_vm.pid):
            self._cleanup_stale_runtime(running_vm)
            return None
        return running_vm
