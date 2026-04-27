from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.ai.types import (
    AssistantMessage,
    AssistantStreamEvent,
    Context,
    ImageContent,
    Message,
    Model,
    StreamOptions,
    TextContent,
    ToolCall,
    ToolResultMessage,
    ToolSpec,
)

ToolExecutionMode = Literal["sequential", "parallel"]
QueueMode = Literal["all", "one-at-a-time"]


class AgentToolResult(BaseModel):
    content: list[TextContent | ImageContent]
    details: Any = None
    terminate: bool = False


ToolUpdateCallback = Callable[[AgentToolResult], None]
ToolExecute = Callable[[str, dict[str, Any], ToolUpdateCallback | None], Awaitable[AgentToolResult]]
PrepareArguments = Callable[[dict[str, Any]], dict[str, Any]]


class AgentTool(ToolSpec):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    label: str
    execute: ToolExecute = Field(exclude=True)
    prepare_arguments: PrepareArguments | None = Field(default=None, exclude=True)
    execution_mode: ToolExecutionMode | None = None


class AgentContext(BaseModel):
    system_prompt: str = ""
    messages: list[Message] = Field(default_factory=list)
    tools: list[AgentTool] = Field(default_factory=list)


class AgentState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    system_prompt: str = ""
    model: Model
    thinking_level: str = "off"
    tools: list[AgentTool] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    is_streaming: bool = False
    streaming_message: Message | None = None
    pending_tool_calls: set[str] = Field(default_factory=set)
    error_message: str | None = None


class BeforeToolCallResult(BaseModel):
    block: bool = False
    reason: str | None = None


class AfterToolCallResult(BaseModel):
    content: list[TextContent | ImageContent] | None = None
    details: Any = None
    is_error: bool | None = None
    terminate: bool | None = None


class BeforeToolCallContext(BaseModel):
    assistant_message: AssistantMessage
    tool_call: ToolCall
    args: dict[str, Any]
    context: AgentContext


class AfterToolCallContext(BeforeToolCallContext):
    result: AgentToolResult
    is_error: bool


ConvertToLlm = Callable[[list[Message]], Awaitable[list[Message]] | list[Message]]
TransformContext = Callable[[list[Message]], Awaitable[list[Message]] | list[Message]]
GetQueuedMessages = Callable[[], Awaitable[list[Message]] | list[Message]]
BeforeToolCall = Callable[[BeforeToolCallContext], Awaitable[BeforeToolCallResult | None]]
AfterToolCall = Callable[[AfterToolCallContext], Awaitable[AfterToolCallResult | None]]


class AgentLoopConfig(StreamOptions):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: Model
    convert_to_llm: ConvertToLlm
    transform_context: TransformContext | None = None
    get_api_key: Callable[[str], Awaitable[str | None] | str | None] | None = None
    get_steering_messages: GetQueuedMessages | None = None
    get_follow_up_messages: GetQueuedMessages | None = None
    tool_execution: ToolExecutionMode = "parallel"
    before_tool_call: BeforeToolCall | None = None
    after_tool_call: AfterToolCall | None = None


class AgentEvent(BaseModel):
    type: str
    message: Message | None = None
    messages: list[Message] | None = None
    assistant_message_event: AssistantStreamEvent | None = None
    tool_results: list[ToolResultMessage] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    args: dict[str, Any] | None = None
    partial_result: AgentToolResult | None = None
    result: AgentToolResult | None = None
    is_error: bool | None = None
