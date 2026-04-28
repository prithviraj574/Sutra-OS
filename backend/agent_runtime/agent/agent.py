from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable

from agent_runtime.agent.loop import maybe_await, run_agent_loop, run_agent_loop_continue
from agent_runtime.agent.types import (
    AfterToolCall,
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentState,
    BeforeToolCall,
    ConvertToLlm,
    QueueMode,
    StreamFn,
    ToolExecutionMode,
    TransformContext,
)
from agent_runtime.ai import stream_simple
from agent_runtime.ai.event_stream import AsyncEventStream
from agent_runtime.ai.types import (
    AbortController,
    AbortSignal,
    AssistantMessage,
    Message,
    Model,
    StreamOptions,
    TextContent,
    Usage,
    UserMessage,
)

AgentListener = Callable[..., Awaitable[None] | None]


def default_convert_to_llm(messages: list[AgentMessage]) -> list[Message]:
    return [message for message in messages if message.role in {"user", "assistant", "toolResult"}]


class PendingMessageQueue:
    def __init__(self, mode: QueueMode = "one-at-a-time") -> None:
        self.mode = mode
        self._messages: list[AgentMessage] = []

    def enqueue(self, message: AgentMessage) -> None:
        self._messages.append(message)

    def drain(self) -> list[AgentMessage]:
        if self.mode == "all":
            messages = self._messages[:]
            self._messages.clear()
            return messages
        if not self._messages:
            return []
        return [self._messages.pop(0)]

    def clear(self) -> None:
        self._messages.clear()

    def has_items(self) -> bool:
        return bool(self._messages)


class Agent:
    def __init__(
        self,
        *,
        model: Model,
        system_prompt: str = "",
        messages: list[AgentMessage] | None = None,
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
        stream_fn: StreamFn = stream_simple,
        session_id: str | None = None,
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
        self.stream_fn = stream_fn
        self.session_id = session_id
        self._listeners: set[AgentListener] = set()
        self._steering_queue = PendingMessageQueue(steering_mode)
        self._follow_up_queue = PendingMessageQueue(follow_up_mode)
        self._active_task: asyncio.Task | None = None
        self._active_controller: AbortController | None = None
        self._idle_waiter: asyncio.Future[None] | None = None

    def subscribe(self, listener: AgentListener) -> Callable[[], None]:
        self._listeners.add(listener)

        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    def steer(self, message: AgentMessage) -> None:
        self._steering_queue.enqueue(message)

    def follow_up(self, message: AgentMessage) -> None:
        self._follow_up_queue.enqueue(message)

    def clear_steering_queue(self) -> None:
        self._steering_queue.clear()

    def clear_follow_up_queue(self) -> None:
        self._follow_up_queue.clear()

    def clear_all_queues(self) -> None:
        self.clear_steering_queue()
        self.clear_follow_up_queue()

    def has_queued_messages(self) -> bool:
        return self._steering_queue.has_items() or self._follow_up_queue.has_items()

    @property
    def signal(self) -> AbortSignal | None:
        return self._active_controller.signal if self._active_controller else None

    def abort(self) -> None:
        if self._active_controller:
            self._active_controller.abort()
        if self._active_task:
            self._active_task.cancel()

    async def wait_for_idle(self) -> None:
        if self._idle_waiter:
            await self._idle_waiter

    def reset(self) -> None:
        self.state.messages = []
        self.state.is_streaming = False
        self.state.streaming_message = None
        self.state.pending_tool_calls = set()
        self.state.error_message = None
        self.clear_all_queues()

    async def prompt(self, input: str | AgentMessage | list[AgentMessage]) -> None:
        if self.state.is_streaming:
            raise RuntimeError(
                "Agent is already processing a prompt. Use steer() or follow_up() to queue messages."
            )
        if isinstance(input, str):
            prompts = [self._user_message(input)]
        elif isinstance(input, list):
            prompts = input
        else:
            prompts = [input]
        stream = self.run(prompts)
        await stream.result()

    async def continue_prompt(self) -> None:
        if self.state.is_streaming:
            raise RuntimeError("Agent is already processing. Wait for completion before continuing.")
        if not self.state.messages:
            raise RuntimeError("No messages to continue from")
        last = self.state.messages[-1]
        if last.role == "assistant":
            queued_steering = self._steering_queue.drain()
            if queued_steering:
                stream = self.run(queued_steering)
                await stream.result()
                return
            queued_follow_ups = self._follow_up_queue.drain()
            if queued_follow_ups:
                stream = self.run(queued_follow_ups)
                await stream.result()
                return
            raise RuntimeError("Cannot continue from message role: assistant")
        stream = self.continue_run()
        await stream.result()

    def run(self, prompts: list[AgentMessage]) -> AsyncEventStream[AgentEvent, list[AgentMessage]]:
        return self._start(prompts, continue_existing=False)

    def continue_run(self) -> AsyncEventStream[AgentEvent, list[AgentMessage]]:
        return self._start([], continue_existing=True)

    def _start(
        self, prompts: list[AgentMessage], *, continue_existing: bool
    ) -> AsyncEventStream[AgentEvent, list[AgentMessage]]:
        if self.state.is_streaming:
            raise RuntimeError("Agent is already running")
        events: AsyncEventStream[AgentEvent, list[AgentMessage]] = AsyncEventStream()
        self.state.is_streaming = True
        self.state.streaming_message = None
        self.state.error_message = None
        self._active_controller = AbortController()
        self._idle_waiter = asyncio.get_running_loop().create_future()

        async def emit(event: AgentEvent) -> None:
            self._apply_event(event)
            for listener in list(self._listeners):
                await self._notify_listener(listener, event)
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
                    new_messages = await run_agent_loop_continue(
                        context,
                        config,
                        emit,
                        self._active_controller.signal if self._active_controller else None,
                        self.stream_fn,
                    )
                else:
                    new_messages = await run_agent_loop(
                        prompts,
                        context,
                        config,
                        emit,
                        self._active_controller.signal if self._active_controller else None,
                        self.stream_fn,
                    )
                self.state.messages.extend(new_messages)
                events.end(new_messages)
            except asyncio.CancelledError as exc:
                failure = await self._handle_run_failure(exc, aborted=True, emit=emit)
                events.end([failure])
            except Exception as exc:
                failure = await self._handle_run_failure(exc, aborted=False, emit=emit)
                events.end([failure])
            finally:
                self.state.is_streaming = False
                self.state.streaming_message = None
                self.state.pending_tool_calls = set()
                self._active_controller = None
                self._active_task = None
                if self._idle_waiter and not self._idle_waiter.done():
                    self._idle_waiter.set_result(None)

        self._active_task = asyncio.create_task(runner())
        return events

    def _loop_config(self) -> AgentLoopConfig:
        return AgentLoopConfig(
            **self.stream_options.model_dump(exclude={"session_id"}),
            model=self.state.model,
            convert_to_llm=self.convert_to_llm,
            transform_context=self.transform_context,
            get_api_key=self.get_api_key,
            get_steering_messages=self._steering_queue.drain,
            get_follow_up_messages=self._follow_up_queue.drain,
            before_tool_call=self.before_tool_call,
            after_tool_call=self.after_tool_call,
            tool_execution=self.tool_execution,
            session_id=self.session_id or self.stream_options.session_id,
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

    async def _notify_listener(self, listener: AgentListener, event: AgentEvent) -> None:
        try:
            parameters = inspect.signature(listener).parameters
        except (TypeError, ValueError):
            parameters = {}
        if len(parameters) <= 1:
            await maybe_await(listener(event))
        else:
            await maybe_await(listener(event, self.signal))

    async def _handle_run_failure(
        self, error: BaseException, *, aborted: bool, emit: Callable[[AgentEvent], Awaitable[None]]
    ) -> AgentMessage:
        failure = self._failure_message(error, aborted=aborted)
        self.state.messages.append(failure)
        self.state.error_message = failure.error_message if hasattr(failure, "error_message") else str(error)
        await emit(AgentEvent(type="agent_end", messages=[failure]))
        return failure

    def _failure_message(self, error: BaseException, *, aborted: bool) -> AgentMessage:
        return AssistantMessage(
            content=[TextContent(text="")],
            api=self.state.model.api,
            provider=self.state.model.provider,
            model=self.state.model.id,
            usage=Usage(),
            stop_reason="aborted" if aborted else "error",
            error_message=str(error),
            timestamp=int(time.time() * 1000),
        )

    def _user_message(self, text: str) -> AgentMessage:
        return UserMessage(content=[TextContent(text=text)], timestamp=int(time.time() * 1000))
