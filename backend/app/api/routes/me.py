"""Authenticated user bootstrap endpoints."""

from fastapi import APIRouter

from app.api.deps import PrincipalDep, SessionDep, SettingsDep
from app.api.helpers import list_agents_for_user
from app.api.schemas import AgentResponse, MeResponse, UserResponse
from app.services.users import EnsureUserAgentService, EnsureUserService

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
def get_me(
    session: SessionDep,
    principal: PrincipalDep,
    settings: SettingsDep,
) -> MeResponse:
    user_service = EnsureUserService(session)
    bootstrap_service = EnsureUserAgentService(session, settings)

    try:
        user = user_service.ensure(principal)
        bootstrap_service.ensure_initial_agent(user)
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(user)
    agents = list_agents_for_user(session, user.id)
    return MeResponse(
        user=UserResponse.from_model(user),
        agents=[AgentResponse.from_model(agent) for agent in agents],
    )
