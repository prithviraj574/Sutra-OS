"""Authenticated user bootstrap endpoints."""

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, SessionDep, SettingsDep
from app.api.helpers import list_agents_for_user
from app.api.schemas import AgentResponse, MeResponse, UserResponse
from app.services.users import EnsureUserAgentService

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
def get_me(
    session: SessionDep,
    user: CurrentUserDep,
    settings: SettingsDep,
) -> MeResponse:
    bootstrap_service = EnsureUserAgentService(session, settings)

    try:
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
