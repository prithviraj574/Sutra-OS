from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from agent_runtime.agent.loop import maybe_await, run_agent_loop, run_agent_loop_continue
from agent_runtime.agent.types import (
    AfterToolCall,
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    AgentState,
    BeforeToolCall,
    ConvertToLlm,
    QueueMode,
    ToolExecutionMode,
    TransformContext,
)
from agent_runtime.ai import stream_simple
from agent_runtime.ai.event_stream import AsyncEventStream
from agent_runtime.ai.types import Message, Model, StreamOptions

AgentListener = Callable[[AgentEvent], Awaitable[None] | None]


def default_convert_to_llm(messages: list[Message]) -> list[Message]:
    return [message for message in messages if message.role in {"user", "assistant", "toolResult"}]


class PendingMessageQueue:
    def __init__(self, mode: QueueMode = "one-at-a-time") -> None:
        self.mode = mode
        self._messages: list[Message] = []

    def enqueue(self, message: Message) -> None:
        self._messages.append(message)

    def drain(self) -> list[Message]:
        if self.mode == "all":
            messages = self._messages[:]
            self._messages.clear()
            return messages
        if not self._messages:
            return []
        return [self._messages.pop(0)]

    def clear(self) -> None:
        self._messages.clear()


class Agent:
    def __init__(
        self,
        *,
        model: Model,
        system_prompt: str = "",
        messages: list[Message] | None = None,
        tools: list = None,
        convert_to_llm: ConvertToLlm = default_convert_to_llm,
        transform_context: TransformContext | None = None,
        get_api_key: Callable[[str], Awaitable[str | None] | str | None] | None = None,
        before_tool_call: BeforeToolCall | None = None,
        after_tool_call: AfterToolCall | None = None,
        steering_mode: QueueMode = "one-at-a-time",
        follow_up_mode: QueueMode = "one-at-a-time",
        tool_execution: ToolExecutionMode = "parallel",
        stream_options: StreamOptions | None = None,
    ) -> None:
        self.state = AgentState(
            model=model,
            system_prompt=system_prompt,
            messages=list(messages or []),
            tools=list(tools or []),
        )
        self.convert_to_llm = convert_to_llm
        self.transform_context = transform_context
        self.get_api_key = get_api_key
        self.before_tool_call = before_tool_call
        self.after_tool_call = after_tool_call
        self.tool_execution = tool_execution
        self.stream_options = stream_options or StreamOptions()
        self._listeners: set[AgentListener] = set()
        self._steering_queue = PendingMessageQueue(steering_mode)
        self._follow_up_queue = PendingMessageQueue(follow_up_mode)
        self._active_task: asyncio.Task | None = None

    def subscribe(self, listener: AgentListener) -> Callable[[], None]:
        self._listeners.add(listener)

        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    def steer(self, message: Message) -> None:
        self._steering_queue.enqueue(message)

    def follow_up(self, message: Message) -> None:
        self._follow_up_queue.enqueue(message)

    def abort(self) -> None:
        if self._active_task:
            self._active_task.cancel()

    def run(self, prompts: list[Message]) -> AsyncEventStream[AgentEvent, list[Message]]:
        return self._start(prompts, continue_existing=False)

    def continue_run(self) -> AsyncEventStream[AgentEvent, list[Message]]:
        return self._start([], continue_existing=True)

    def _start(
        self, prompts: list[Message], *, continue_existing: bool
    ) -> AsyncEventStream[AgentEvent, list[Message]]:
        if self.state.is_streaming:
            raise RuntimeError("Agent is already running")
        events: AsyncEventStream[AgentEvent, list[Message]] = AsyncEventStream()
        self.state.is_streaming = True

        async def emit(event: AgentEvent) -> None:
            self._apply_event(event)
            for listener in list(self._listeners):
                await maybe_await(listener(event))
            events.push(event)

        async def runner() -> None:
            try:
                config = self._loop_config()
                context = AgentContext(
                    system_prompt=self.state.system_prompt,
                    messages=self.state.messages,
                    tools=self.state.tools,
                )
                if continue_existing:
                    new_messages = await run_agent_loop_continue(context, config, emit)
                else:
                    new_messages = await run_agent_loop(prompts, context, config, emit)
                self.state.messages.extend(new_messages)
                events.end(new_messages)
            finally:
                self.state.is_streaming = False
                self._active_task = None

        self._active_task = asyncio.create_task(runner())
        return events

    def _loop_config(self) -> AgentLoopConfig:
        return AgentLoopConfig(
            **self.stream_options.model_dump(),
            model=self.state.model,
            convert_to_llm=self.convert_to_llm,
            transform_context=self.transform_context,
            get_api_key=self.get_api_key,
            get_steering_messages=self._steering_queue.drain,
            get_follow_up_messages=self._follow_up_queue.drain,
            before_tool_call=self.before_tool_call,
            after_tool_call=self.after_tool_call,
            tool_execution=self.tool_execution,
        )

    def _apply_event(self, event: AgentEvent) -> None:
        if event.type == "message_update" and event.message is not None:
            self.state.streaming_message = event.message
        elif event.type == "tool_execution_start" and event.tool_call_id:
            self.state.pending_tool_calls.add(event.tool_call_id)
        elif event.type == "tool_execution_end" and event.tool_call_id:
            self.state.pending_tool_calls.discard(event.tool_call_id)
        elif event.type == "message_end" and event.message is not None:
            self.state.streaming_message = None
            if getattr(event.message, "stop_reason", None) == "error":
                self.state.error_message = getattr(event.message, "error_message", None)
