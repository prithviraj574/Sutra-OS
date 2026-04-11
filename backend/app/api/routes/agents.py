"""Agent management endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import PrincipalDep, SessionDep, SettingsDep
from app.api.helpers import list_agents_for_user
from app.api.schemas import AgentCreateRequest, AgentResponse
from app.models.models import User
from app.services.users import CreateAgentService

router = APIRouter(tags=["agents"])


@router.get("/agents", response_model=list[AgentResponse])
def list_agents(
    session: SessionDep,
    principal: PrincipalDep,
) -> list[AgentResponse]:
    user = session.exec(
        select(User).where(User.firebase_uid == principal.firebase_uid)
    ).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return [AgentResponse.from_model(agent) for agent in list_agents_for_user(session, user.id)]


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreateRequest,
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
) -> AgentResponse:
    user = session.exec(
        select(User).where(User.firebase_uid == principal.firebase_uid)
    ).one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User must be initialized via /me before creating agents",
        )

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
