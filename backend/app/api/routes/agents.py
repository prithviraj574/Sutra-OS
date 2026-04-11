"""Agent management endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, SessionDep, SettingsDep
from app.api.helpers import list_agents_for_user
from app.api.schemas import AgentCreateRequest, AgentResponse
from app.services.users import CreateAgentService

router = APIRouter(tags=["agents"])


@router.get("/agents", response_model=list[AgentResponse])
def list_agents(
    session: SessionDep,
    user: CurrentUserDep,
) -> list[AgentResponse]:
    return [AgentResponse.from_model(agent) for agent in list_agents_for_user(session, user.id)]


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreateRequest,
    session: SessionDep,
    user: CurrentUserDep,
    settings: SettingsDep,
) -> AgentResponse:
    try:
        agent = CreateAgentService(session, settings).create(user_id=user.id, name=payload.name)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception:
        session.rollback()
        raise

    session.refresh(agent)
    return AgentResponse.from_model(agent)
