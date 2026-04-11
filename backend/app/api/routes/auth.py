"""Authentication exchange endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep, SettingsDep
from app.api.helpers import list_agents_for_user
from app.api.schemas import AuthExchangeRequest, AuthExchangeResponse, AgentResponse, UserResponse
from app.core.auth import authenticate_external_principal, issue_access_token
from app.services.users import EnsureUserAgentService, EnsureUserService

router = APIRouter(tags=["auth"])


@router.post("/auth/exchange", response_model=AuthExchangeResponse)
def exchange_auth_token(
    payload: AuthExchangeRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> AuthExchangeResponse:
    external_principal = authenticate_external_principal(payload.id_token, settings)

    try:
        user = EnsureUserService(session).ensure(external_principal)
        EnsureUserAgentService(session, settings).ensure_initial_agent(user)
        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise

    session.refresh(user)
    agents = list_agents_for_user(session, user.id)
    access_token, expires_in = issue_access_token(user, settings)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not issue access token",
        )

    return AuthExchangeResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserResponse.from_model(user),
        agents=[AgentResponse.from_model(agent) for agent in agents],
    )
