from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.runtime.host_client import HostManagerClient
from app.runtime.schemas import AgentRuntimeResponse
from app.runtime.service import RuntimeService
from app.runtime.settings import RuntimeSettings

router = APIRouter(prefix="/internal/agents", tags=["runtime"])


def get_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings.from_env()


def get_host_manager_client(
    settings: RuntimeSettings = Depends(get_runtime_settings),
) -> HostManagerClient:
    return HostManagerClient(
        base_url=settings.host_base_url,
        api_key=settings.api_key,
    )


def get_runtime_service(
    session: Session = Depends(get_session),
    host_client: HostManagerClient = Depends(get_host_manager_client),
    settings: RuntimeSettings = Depends(get_runtime_settings),
) -> RuntimeService:
    return RuntimeService(
        session=session,
        host_client=host_client,
        host_instance_name=settings.host_instance_name,
    )


@router.post("/{agent_id}/runtime/ensure", response_model=AgentRuntimeResponse)
async def ensure_runtime(
    agent_id: UUID,
    service: RuntimeService = Depends(get_runtime_service),
) -> AgentRuntimeResponse:
    try:
        return await service.ensure_runtime(agent_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{agent_id}/runtime/stop", response_model=AgentRuntimeResponse)
async def stop_runtime(
    agent_id: UUID,
    service: RuntimeService = Depends(get_runtime_service),
) -> AgentRuntimeResponse:
    try:
        return await service.stop_runtime(agent_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{agent_id}/runtime/status", response_model=AgentRuntimeResponse)
async def runtime_status(
    agent_id: UUID,
    service: RuntimeService = Depends(get_runtime_service),
) -> AgentRuntimeResponse:
    try:
        return await service.get_runtime_status(agent_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
