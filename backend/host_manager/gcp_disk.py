import asyncio
import logging
import time
from pathlib import Path

from google.api_core.exceptions import AlreadyExists
from google.cloud import compute_v1

logger = logging.getLogger(__name__)


class GCPPersistentDiskManager:
    def __init__(
        self,
        project_id: str,
        zone: str,
        host_instance_name: str,
        disk_size_gb: int = 20,
        disk_type: str = "pd-balanced",
        device_wait_timeout_s: int = 60,
    ):
        self.project_id = project_id
        self.zone = zone
        self.host_instance_name = host_instance_name
        self.disk_size_gb = disk_size_gb
        self.disk_type = disk_type
        self.device_wait_timeout_s = device_wait_timeout_s
        self.disks_client = compute_v1.DisksClient()
        self.instances_client = compute_v1.InstancesClient()

    def disk_name(self, agent_id: str) -> str:
        return f"agent-{agent_id}"

    async def ensure_disk(self, agent_id: str) -> str:
        disk_name = self.disk_name(agent_id)
        try:
            self.disks_client.get(
                project=self.project_id,
                zone=self.zone,
                disk=disk_name,
            )
            return disk_name
        except Exception:
            pass

        disk_type_url = f"zones/{self.zone}/diskTypes/{self.disk_type}"
        disk = compute_v1.Disk(
            name=disk_name,
            size_gb=self.disk_size_gb,
            type_=disk_type_url,
            labels={"agent-id": agent_id[:63], "managed-by": "sutra"},
        )

        try:
            operation = self.disks_client.insert(
                project=self.project_id,
                zone=self.zone,
                disk_resource=disk,
            )
            await asyncio.to_thread(operation.result)
        except AlreadyExists:
            logger.info("Disk %s already exists", disk_name)

        return disk_name

    async def ensure_attached(self, disk_name: str) -> str:
        instance = self.instances_client.get(
            project=self.project_id,
            zone=self.zone,
            instance=self.host_instance_name,
        )
        if any(d.device_name == disk_name for d in instance.disks):
            return disk_name

        attached_disk = compute_v1.AttachedDisk(
            source=f"projects/{self.project_id}/zones/{self.zone}/disks/{disk_name}",
            device_name=disk_name,
            mode="READ_WRITE",
            auto_delete=False,
        )
        operation = self.instances_client.attach_disk(
            project=self.project_id,
            zone=self.zone,
            instance=self.host_instance_name,
            attached_disk_resource=attached_disk,
        )
        await asyncio.to_thread(operation.result)
        return disk_name

    async def wait_for_device(self, disk_name: str) -> str:
        device_path = self.host_device_path(disk_name)
        deadline = time.monotonic() + self.device_wait_timeout_s
        while time.monotonic() < deadline:
            if Path(device_path).exists():
                return device_path
            await asyncio.sleep(1)
        raise TimeoutError(f"Disk device {device_path} did not appear within {self.device_wait_timeout_s}s")

    async def detach(self, disk_name: str) -> None:
        instance = self.instances_client.get(
            project=self.project_id,
            zone=self.zone,
            instance=self.host_instance_name,
        )
        if not any(d.device_name == disk_name for d in instance.disks):
            return

        operation = self.instances_client.detach_disk(
            project=self.project_id,
            zone=self.zone,
            instance=self.host_instance_name,
            device_name=disk_name,
        )
        await asyncio.to_thread(operation.result)

    def host_device_path(self, disk_name: str) -> str:
        return f"/dev/disk/by-id/google-{disk_name}"
