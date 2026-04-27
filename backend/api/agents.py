from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from agent_runtime import service
from agent_runtime.repository import AgentRepository
from agent_runtime.settings import Settings
from api.deps import get_repository, get_settings
from api.schemas import MessagesResponse, SessionCreate, SessionCreated, UserInput

router = APIRouter(prefix="/v1/agent", tags=["agent"])


@router.post("/sessions", response_model=SessionCreated)
async def create_session(
    request: SessionCreate,
    repo: AgentRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> SessionCreated:
    session = await service.create_session(
        repo,
        settings,
        user_id=request.user_id,
        system_prompt=request.system_prompt,
        model=request.model,
    )
    return SessionCreated(session_id=session.id, user_id=session.user_id)


@router.get("/sessions/{session_id}/messages", response_model=MessagesResponse)
async def list_messages(
    session_id: str,
    user_id: str,
    repo: AgentRepository = Depends(get_repository),
) -> MessagesResponse:
    session = await repo.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return MessagesResponse(
        session_id=session_id,
        messages=await repo.list_messages(session_id=session_id, user_id=user_id),
    )


@router.post("/sessions/{session_id}/messages", response_model=None)
async def send_message(
    session_id: str,
    request: UserInput,
    repo: AgentRepository = Depends(get_repository),
) -> MessagesResponse | StreamingResponse:
    session = await repo.get_session(session_id=session_id, user_id=request.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if request.stream:
        return StreamingResponse(
            service.run_sse(repo, session, user_id=request.user_id, content=request.content),
            media_type="text/event-stream",
        )
    messages = await service.run_once(repo, session, user_id=request.user_id, content=request.content)
    return MessagesResponse(session_id=session_id, messages=messages)
