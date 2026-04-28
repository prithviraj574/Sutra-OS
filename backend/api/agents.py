from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from agent_runtime import service
from agent_runtime.store import AgentStore
from api.deps import get_agent_config, get_store
from api.schemas import (
    AgentCreate,
    AgentSummary,
    MessagesResponse,
    SessionCreate,
    SessionCreated,
    SessionSummary,
    UserInput,
)
from config import AgentConfig

router = APIRouter(prefix="/v1/agent", tags=["agent"])


@router.get("/agents", response_model=list[AgentSummary])
async def list_agents(
    user_id: str,
    store: AgentStore = Depends(get_store),
) -> list[AgentSummary]:
    return [AgentSummary.model_validate(agent) for agent in await store.list_agents(user_id=user_id)]


@router.post("/agents", response_model=AgentSummary)
async def create_agent(
    request: AgentCreate,
    store: AgentStore = Depends(get_store),
) -> AgentSummary:
    agent = await store.create_agent(user_id=request.user_id, name=request.name)
    return AgentSummary.model_validate(agent)


@router.get("/agents/{agent_id}/sessions", response_model=list[SessionSummary])
async def list_sessions(
    agent_id: str,
    user_id: str,
    store: AgentStore = Depends(get_store),
) -> list[SessionSummary]:
    agent = await store.get_agent(agent_id=agent_id, user_id=user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    sessions = await store.list_sessions(user_id=user_id, agent_id=agent_id)
    return [SessionSummary.model_validate(session) for session in sessions]


@router.post("/agents/{agent_id}/sessions", response_model=SessionCreated)
async def create_session(
    agent_id: str,
    request: SessionCreate,
    store: AgentStore = Depends(get_store),
    agent_config: AgentConfig = Depends(get_agent_config),
) -> SessionCreated:
    session = await service.create_session(
        store,
        agent_config,
        user_id=request.user_id,
        agent_id=agent_id,
        system_prompt=request.system_prompt,
        model=request.model,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Agent not found")
    return SessionCreated(session_id=session.id, agent_id=session.agent_id, user_id=session.user_id)


@router.get("/sessions/{session_id}/messages", response_model=MessagesResponse)
async def list_messages(
    session_id: str,
    user_id: str,
    store: AgentStore = Depends(get_store),
) -> MessagesResponse:
    session = await store.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return MessagesResponse(
        session_id=session_id,
        messages=await store.get_messages(session_id=session_id, user_id=user_id),
    )


@router.post("/sessions/{session_id}/messages", response_model=None)
async def send_message(
    session_id: str,
    request: UserInput,
    store: AgentStore = Depends(get_store),
) -> MessagesResponse | StreamingResponse:
    session = await store.get_session(session_id=session_id, user_id=request.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if request.stream:
        return StreamingResponse(
            service.run_sse(store, session, user_id=request.user_id, content=request.content),
            media_type="text/event-stream",
        )
    messages = await service.run_once(store, session, user_id=request.user_id, content=request.content)
    return MessagesResponse(session_id=session_id, messages=messages)
