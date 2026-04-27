from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from agent_runtime.agent import Agent
from agent_runtime.agent.types import AgentEvent
from agent_runtime.ai.env_keys import get_env_api_key
from agent_runtime.ai.types import Model, UserMessage
from agent_runtime.repository import AgentRepository
from agent_runtime.settings import Settings
from agent_runtime.tools import default_tools


def now_ms() -> int:
    return int(time.time() * 1000)


def default_model(settings: Settings) -> Model:
    return Model(
        id=settings.default_model,
        name=settings.default_model,
        api=settings.default_api,
        provider=settings.default_provider,
        base_url="",
        reasoning=False,
        input=["text"],
    )


async def create_session(
    repo: AgentRepository,
    settings: Settings,
    *,
    user_id: str,
    system_prompt: str | None,
    model: dict[str, Any] | None,
):
    return await repo.create_session(
        user_id=user_id,
        system_prompt=system_prompt or settings.default_system_prompt,
        model=model or default_model(settings).model_dump(mode="json"),
    )


async def run_once(
    repo: AgentRepository,
    session: Any,
    *,
    user_id: str,
    content: str,
) -> list[Any]:
    emitted: list[AgentEvent] = []
    agent = await hydrate_agent(repo, session, user_id=user_id)
    agent.subscribe(emitted.append)
    stream = agent.run([UserMessage(content=content, timestamp=now_ms())])
    messages = await stream.result()
    await persist_run(repo, session, user_id=user_id, messages=messages, events=emitted)
    return messages


async def run_sse(
    repo: AgentRepository,
    session: Any,
    *,
    user_id: str,
    content: str,
) -> AsyncIterator[str]:
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
    agent = await hydrate_agent(repo, session, user_id=user_id)
    emitted: list[AgentEvent] = []

    async def on_event(event: AgentEvent) -> None:
        emitted.append(event)
        await repo.append_event(
            session_id=session.id,
            user_id=user_id,
            event_type=event.type,
            payload=event.model_dump(mode="json"),
        )
        await queue.put(event)

    agent.subscribe(on_event)

    async def runner() -> None:
        try:
            stream = agent.run([UserMessage(content=content, timestamp=now_ms())])
            messages = await stream.result()
            await repo.append_messages(session_id=session.id, user_id=user_id, messages=messages)
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield to_sse(event.type, event.model_dump(mode="json"))
    finally:
        await task


async def hydrate_agent(repo: AgentRepository, session: Any, *, user_id: str) -> Agent:
    return Agent(
        model=Model.model_validate(session.model),
        system_prompt=session.system_prompt,
        messages=await repo.list_messages(session_id=session.id, user_id=user_id),
        tools=default_tools(),
        get_api_key=get_env_api_key,
    )


async def persist_run(
    repo: AgentRepository,
    session: Any,
    *,
    user_id: str,
    messages: list[Any],
    events: list[AgentEvent],
) -> None:
    await repo.append_messages(session_id=session.id, user_id=user_id, messages=messages)
    for event in events:
        await repo.append_event(
            session_id=session.id,
            user_id=user_id,
            event_type=event.type,
            payload=event.model_dump(mode="json"),
        )


def to_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
