from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


KnownApi = Literal[
    "openai-completions",
    "mistral-conversations",
    "openai-responses",
    "azure-openai-responses",
    "openai-codex-responses",
    "anthropic-messages",
    "bedrock-converse-stream",
    "google-generative-ai",
    "google-gemini-cli",
    "google-vertex",
    "faux",
]

ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]
StopReason = Literal["stop", "length", "toolUse", "error", "aborted"]
Transport = Literal["sse", "websocket", "auto"]
CacheRetention = Literal["none", "short", "long"]


class AbortSignal:
    def __init__(self) -> None:
        self.aborted = False

    def throw_if_aborted(self) -> None:
        if self.aborted:
            raise asyncio.CancelledError("Request aborted")


class AbortController:
    def __init__(self) -> None:
        self.signal = AbortSignal()

    def abort(self) -> None:
        self.signal.aborted = True


class ProviderResponse(BaseModel):
    status: int
    headers: dict[str, str] = Field(default_factory=dict)


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str
    text_signature: str | None = None


class ThinkingContent(BaseModel):
    type: Literal["thinking"] = "thinking"
    thinking: str
    thinking_signature: str | None = None
    redacted: bool = False


class ImageContent(BaseModel):
    type: Literal["image"] = "image"
    data: str
    mime_type: str


class ToolCall(BaseModel):
    type: Literal["toolCall"] = "toolCall"
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    thought_signature: str | None = None


AssistantContent = TextContent | ThinkingContent | ToolCall
ToolResultContent = TextContent | ImageContent


class UsageCost(BaseModel):
    input: float = 0
    output: float = 0
    cache_read: float = 0
    cache_write: float = 0
    total: float = 0


class Usage(BaseModel):
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total_tokens: int = 0
    cost: UsageCost = Field(default_factory=UsageCost)


class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: str | list[TextContent | ImageContent]
    timestamp: int


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: list[AssistantContent] = Field(default_factory=list)
    api: str
    provider: str
    model: str
    usage: Usage = Field(default_factory=Usage)
    stop_reason: StopReason = "stop"
    timestamp: int
    response_id: str | None = None
    error_message: str | None = None


class ToolResultMessage(BaseModel):
    role: Literal["toolResult"] = "toolResult"
    tool_call_id: str
    tool_name: str
    content: list[ToolResultContent]
    is_error: bool
    timestamp: int
    details: Any = None


# Provider-facing LLM message shape. This mirrors pi-ai's Message type.
# Agent runtime events live in agent_runtime.agent.types.AgentEvent.
Message = UserMessage | AssistantMessage | ToolResultMessage


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})


class Context(BaseModel):
    system_prompt: str | None = None
    messages: list[Message] = Field(default_factory=list)
    tools: list[ToolSpec] = Field(default_factory=list)


class Model(BaseModel):
    id: str
    name: str
    api: str
    provider: str
    base_url: str = ""
    reasoning: bool = False
    input: list[Literal["text", "image"]] = Field(default_factory=lambda: ["text"])
    cost: dict[str, float] = Field(
        default_factory=lambda: {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
    )
    context_window: int = 0
    max_tokens: int = 0
    headers: dict[str, str] = Field(default_factory=dict)
    compat: dict[str, Any] = Field(default_factory=dict)


class StreamOptions(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    temperature: float | None = None
    max_tokens: int | None = None
    api_key: str | None = None
    signal: AbortSignal | None = Field(default=None, exclude=True)
    transport: Transport = "sse"
    cache_retention: CacheRetention = "short"
    session_id: str | None = None
    on_payload: Callable[[Any, Any], Any] | None = Field(default=None, exclude=True)
    on_response: Callable[[ProviderResponse, Any], Any] | None = Field(default=None, exclude=True)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int | None = None
    max_retries: int | None = None
    max_retry_delay_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    reasoning: ThinkingLevel = "off"
    thinking_budgets: dict[str, int] = Field(default_factory=dict)


class AssistantStreamEvent(BaseModel):
    type: Literal[
        "start",
        "text_start",
        "text_delta",
        "text_end",
        "thinking_start",
        "thinking_delta",
        "thinking_end",
        "toolcall_start",
        "toolcall_delta",
        "toolcall_end",
        "done",
        "error",
    ]
    partial: AssistantMessage | None = None
    message: AssistantMessage | None = None
    error: AssistantMessage | None = None
    reason: StopReason | None = None
    content_index: int | None = None
    delta: str | None = None
    content: str | None = None
    tool_call: ToolCall | None = None


class AssistantMessageEventStream(Protocol):
    def __aiter__(self) -> AsyncIterator[AssistantStreamEvent]: ...

    async def result(self) -> AssistantMessage: ...
