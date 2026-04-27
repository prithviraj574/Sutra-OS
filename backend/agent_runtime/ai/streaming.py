from __future__ import annotations

from agent_runtime.ai.registry import get_api_provider
from agent_runtime.ai.types import AssistantMessage, AssistantMessageEventStream, Context, Model, StreamOptions


def stream(model: Model, context: Context, options: StreamOptions | None = None) -> AssistantMessageEventStream:
    provider = get_api_provider(model.api)
    if provider is None:
        raise RuntimeError(f"No API provider registered for api: {model.api}")
    return provider.stream(model, context, options or StreamOptions())


async def complete(model: Model, context: Context, options: StreamOptions | None = None) -> AssistantMessage:
    return await stream(model, context, options).result()


def stream_simple(
    model: Model, context: Context, options: StreamOptions | None = None
) -> AssistantMessageEventStream:
    provider = get_api_provider(model.api)
    if provider is None:
        raise RuntimeError(f"No API provider registered for api: {model.api}")
    return provider.stream_simple(model, context, options or StreamOptions())


async def complete_simple(
    model: Model, context: Context, options: StreamOptions | None = None
) -> AssistantMessage:
    return await stream_simple(model, context, options).result()
