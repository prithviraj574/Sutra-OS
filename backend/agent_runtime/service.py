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
from agent_runtime.store import AgentStore
from agent_runtime.tools import default_tools
from config import AgentConfig


def now_ms() -> int:
    return int(time.time() * 1000)


def default_model(config: AgentConfig) -> Model:
    return Model(
        id=config.default_model,
        name=config.default_model,
        api=config.default_api,
        provider=config.default_provider,
        base_url="",
        reasoning=False,
        input=["text"],
    )


async def create_session(
    store: AgentStore,
    config: AgentConfig,
    *,
    user_id: str,
    agent_id: str,
    system_prompt: str | None,
    model: dict[str, Any] | None,
):
    return await store.create_session(
        user_id=user_id,
        agent_id=agent_id,
        system_prompt=system_prompt or config.default_system_prompt,
        model=model or default_model(config).model_dump(mode="json"),
        tools=[],
    )


async def run_once(
    store: AgentStore,
    session: Any,
    *,
    user_id: str,
    content: str,
) -> list[Any]:
    agent = await hydrate_agent(store, session, user_id=user_id)
    stream = agent.run([UserMessage(content=content, timestamp=now_ms())])
    new_messages = await stream.result()
    all_messages = [*agent.state.messages[: -len(new_messages)], *new_messages] if new_messages else agent.state.messages
    await store.save_messages(session_id=session.id, user_id=user_id, messages=all_messages)
    return new_messages


async def run_sse(
    store: AgentStore,
    session: Any,
    *,
    user_id: str,
    content: str,
) -> AsyncIterator[str]:
    queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
    agent = await hydrate_agent(store, session, user_id=user_id)

    async def on_event(event: AgentEvent) -> None:
        await queue.put(event)

    agent.subscribe(on_event)

    async def runner() -> None:
        try:
            stream = agent.run([UserMessage(content=content, timestamp=now_ms())])
            new_messages = await stream.result()
            all_messages = (
                [*agent.state.messages[: -len(new_messages)], *new_messages]
                if new_messages
                else agent.state.messages
            )
            await store.save_messages(session_id=session.id, user_id=user_id, messages=all_messages)
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


async def hydrate_agent(store: AgentStore, session: Any, *, user_id: str) -> Agent:
    agent = await store.get_agent(agent_id=session.agent_id, user_id=user_id)
    if agent is None:
        raise RuntimeError("Agent not found for session")
    return Agent(
        model=Model.model_validate(session.model),
        system_prompt=session.system_prompt,
        messages=await store.get_messages(session_id=session.id, user_id=user_id),
        tools=default_tools(),
        get_api_key=get_env_api_key,
    )


def to_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
