from fastapi import FastAPI, Header, HTTPException

from host_manager.config import HostRuntimeConfig
from host_manager.firecracker import FirecrackerManager
from host_manager.gcp_disk import GCPPersistentDiskManager
from host_manager.schemas import HostAgentResponse

config = HostRuntimeConfig.from_env()
disk_manager = GCPPersistentDiskManager(
    project_id=config.project_id,
    zone=config.zone,
    host_instance_name=config.host_instance_name,
    disk_size_gb=config.disk_size_gb,
    disk_type=config.disk_type,
    device_wait_timeout_s=config.device_wait_timeout_s,
)
firecracker_manager = FirecrackerManager(config)

app = FastAPI(title="Sutra Runtime Host Manager")


def verify_api_key(x_api_key: str) -> None:
    if config.api_key and x_api_key != config.api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def stopped_response(agent_id: str) -> HostAgentResponse:
    return HostAgentResponse(
        agent_id=agent_id,
        state="stopped",
        pd_name=disk_manager.disk_name(agent_id),
        host_instance_name=config.host_instance_name,
    )


@app.post("/agents/{agent_id}/ensure", response_model=HostAgentResponse)
async def ensure_agent(agent_id: str, x_api_key: str = Header(...)) -> HostAgentResponse:
    verify_api_key(x_api_key)

    existing_vm = firecracker_manager.status(agent_id)
    if existing_vm is not None:
        return HostAgentResponse(
            agent_id=agent_id,
            state="running",
            pd_name=existing_vm.pd_name,
            host_instance_name=config.host_instance_name,
            firecracker_id=existing_vm.firecracker_id,
            guest_ip=existing_vm.guest_ip,
            booted_at=existing_vm.booted_at,
            ready=await firecracker_manager.is_ready(agent_id),
        )

    pd_name = await disk_manager.ensure_disk(agent_id)
    await disk_manager.ensure_attached(pd_name)
    device_path = await disk_manager.wait_for_device(pd_name)
    firecracker_manager.ensure_disk_formatted(device_path)
    running_vm = await firecracker_manager.start(
        agent_id=agent_id,
        pd_name=pd_name,
        workspace_device=device_path,
    )

    return HostAgentResponse(
        agent_id=agent_id,
        state="running",
        pd_name=pd_name,
        host_instance_name=config.host_instance_name,
        firecracker_id=running_vm.firecracker_id,
        guest_ip=running_vm.guest_ip,
        booted_at=running_vm.booted_at,
        ready=await firecracker_manager.is_ready(agent_id),
    )


@app.post("/agents/{agent_id}/stop", response_model=HostAgentResponse)
async def stop_agent(agent_id: str, x_api_key: str = Header(...)) -> HostAgentResponse:
    verify_api_key(x_api_key)
    firecracker_manager.stop(agent_id)
    return stopped_response(agent_id)


@app.get("/agents/{agent_id}/status", response_model=HostAgentResponse)
async def agent_status(agent_id: str, x_api_key: str = Header(...)) -> HostAgentResponse:
    verify_api_key(x_api_key)
    running_vm = firecracker_manager.status(agent_id)
    if running_vm is None:
        return stopped_response(agent_id)

    return HostAgentResponse(
        agent_id=agent_id,
        state="running",
        pd_name=running_vm.pd_name,
        host_instance_name=config.host_instance_name,
        firecracker_id=running_vm.firecracker_id,
        guest_ip=running_vm.guest_ip,
        booted_at=running_vm.booted_at,
        ready=await firecracker_manager.is_ready(agent_id),
    )


@app.get("/healthz")
async def healthz() -> dict[str, int | str]:
    return {
        "status": "ok",
        "running_vms": len(firecracker_manager.running_vms),
    }
