"""Chat thread and message endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, SessionDep
from app.api.helpers import list_threads_for_user
from app.api.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatThreadCreateRequest,
    ChatThreadResponse,
)
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])


@router.get("/threads", response_model=list[ChatThreadResponse])
def list_threads(
    session: SessionDep,
    user: CurrentUserDep,
) -> list[ChatThreadResponse]:
    return [ChatThreadResponse.from_model(thread) for thread in list_threads_for_user(session, user.id)]


@router.post("/threads", response_model=ChatThreadResponse, status_code=status.HTTP_201_CREATED)
def create_thread(
    payload: ChatThreadCreateRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> ChatThreadResponse:
    service = ChatService(session)

    try:
        thread = service.create_thread(
            user_id=user.id,
            agent_id=payload.agent_id,
            title=payload.title,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception:
        session.rollback()
        raise

    session.refresh(thread)
    return ChatThreadResponse.from_model(thread)


@router.post("/threads/{thread_id}/messages", response_model=ChatMessageResponse)
def send_message(
    thread_id: UUID,
    payload: ChatMessageRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> ChatMessageResponse:
    service = ChatService(session)

    try:
        result = service.send_message(
            user_id=user.id,
            thread_id=thread_id,
            message=payload.message,
            runtime_env=payload.runtime_env,
            model=payload.model,
            provider=payload.provider,
            base_url=payload.base_url,
            api_key=payload.api_key,
            user_home_path=payload.user_home_path,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        detail = str(exc)
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        if detail in {"Thread not found", "Thread agent not found"}:
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception:
        session.rollback()
        raise

    return ChatMessageResponse(
        thread_id=result.thread_id,
        session_id=result.session_id,
        response_text=result.response_text,
        raw_result=result.raw_result,
    )
