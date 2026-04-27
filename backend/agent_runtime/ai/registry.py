from __future__ import annotations

from collections.abc import Callable

from agent_runtime.ai.types import AssistantMessageEventStream, Context, Model, StreamOptions

StreamFunction = Callable[[Model, Context, StreamOptions], AssistantMessageEventStream]


class ApiProvider:
    def __init__(self, api: str, stream: StreamFunction, stream_simple: StreamFunction | None = None):
        self.api = api
        self.stream = stream
        self.stream_simple = stream_simple or stream


_providers: dict[str, ApiProvider] = {}


def register_api_provider(provider: ApiProvider) -> None:
    _providers[provider.api] = provider


def get_api_provider(api: str) -> ApiProvider | None:
    return _providers.get(api)


def get_api_providers() -> list[ApiProvider]:
    return list(_providers.values())


def clear_api_providers() -> None:
    _providers.clear()
