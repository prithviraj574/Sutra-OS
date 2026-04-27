from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any

from jsonschema import ValidationError, validate

from agent_runtime.agent.types import (
    AfterToolCallContext,
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    AgentTool,
    AgentToolResult,
    BeforeToolCallContext,
)
from agent_runtime.ai import stream_simple
from agent_runtime.ai.types import (
    AssistantMessage,
    Context,
    Message,
    StreamOptions,
    TextContent,
    ToolCall,
    ToolResultMessage,
)

AgentEventSink = Callable[[AgentEvent], Awaitable[None] | None]


def now_ms() -> int:
    return int(time.time() * 1000)


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def run_agent_loop(
    prompts: list[Message],
    context: AgentContext,
    config: AgentLoopConfig,
    emit: AgentEventSink,
) -> list[Message]:
    new_messages = list(prompts)
    current = context.model_copy(update={"messages": [*context.messages, *prompts]})
    await maybe_await(emit(AgentEvent(type="agent_start")))
    await maybe_await(emit(AgentEvent(type="turn_start")))
    for prompt in prompts:
        await maybe_await(emit(AgentEvent(type="message_start", message=prompt)))
        await maybe_await(emit(AgentEvent(type="message_end", message=prompt)))
    await _run_loop(current, new_messages, config, emit)
    return new_messages


async def run_agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
    emit: AgentEventSink,
) -> list[Message]:
    if not context.messages:
        raise ValueError("Cannot continue: no messages in context")
    if isinstance(context.messages[-1], AssistantMessage):
        raise ValueError("Cannot continue from message role: assistant")
    new_messages: list[Message] = []
    await maybe_await(emit(AgentEvent(type="agent_start")))
    await maybe_await(emit(AgentEvent(type="turn_start")))
    await _run_loop(context, new_messages, config, emit)
    return new_messages


async def _run_loop(
    current: AgentContext,
    new_messages: list[Message],
    config: AgentLoopConfig,
    emit: AgentEventSink,
) -> None:
    first_turn = True
    pending = await _queued(config.get_steering_messages)
    while True:
        has_more_tool_calls = True
        while has_more_tool_calls or pending:
            if first_turn:
                first_turn = False
            else:
                await maybe_await(emit(AgentEvent(type="turn_start")))

            for message in pending:
                await maybe_await(emit(AgentEvent(type="message_start", message=message)))
                await maybe_await(emit(AgentEvent(type="message_end", message=message)))
                current.messages.append(message)
                new_messages.append(message)
            pending = []

            assistant = await _stream_assistant_response(current, config, emit)
            new_messages.append(assistant)

            if assistant.stop_reason in {"error", "aborted"}:
                await maybe_await(emit(AgentEvent(type="turn_end", message=assistant, tool_results=[])))
                await maybe_await(emit(AgentEvent(type="agent_end", messages=new_messages)))
                return

            tool_calls = [part for part in assistant.content if isinstance(part, ToolCall)]
            tool_results: list[ToolResultMessage] = []
            has_more_tool_calls = False
            if tool_calls:
                executed = await _execute_tool_calls(current, assistant, tool_calls, config, emit)
                tool_results.extend(executed[0])
                has_more_tool_calls = not executed[1]
                for result in tool_results:
                    current.messages.append(result)
                    new_messages.append(result)

            await maybe_await(
                emit(AgentEvent(type="turn_end", message=assistant, tool_results=tool_results))
            )
            pending = await _queued(config.get_steering_messages)

        follow_ups = await _queued(config.get_follow_up_messages)
        if follow_ups:
            pending = follow_ups
            continue
        break
    await maybe_await(emit(AgentEvent(type="agent_end", messages=new_messages)))


async def _queued(getter: Callable[[], Any] | None) -> list[Message]:
    if getter is None:
        return []
    return list(await maybe_await(getter()) or [])


async def _stream_assistant_response(
    context: AgentContext, config: AgentLoopConfig, emit: AgentEventSink
) -> AssistantMessage:
    messages = context.messages
    if config.transform_context:
        messages = await maybe_await(config.transform_context(messages))
    llm_messages = await maybe_await(config.convert_to_llm(messages))
    api_key = await maybe_await(config.get_api_key(config.model.provider)) if config.get_api_key else None
    llm_context = Context(
        system_prompt=context.system_prompt,
        messages=llm_messages,
        tools=context.tools,
    )
    options = StreamOptions(**config.model_dump(exclude={"model", "convert_to_llm"}))
    options.api_key = api_key or options.api_key
    response = stream_simple(config.model, llm_context, options)
    partial_added = False
    for_event_message: AssistantMessage | None = None
    async for event in response:
        if event.type == "start" and event.partial:
            for_event_message = event.partial
            context.messages.append(for_event_message)
            partial_added = True
            await maybe_await(emit(AgentEvent(type="message_start", message=for_event_message)))
        elif event.type in {
            "text_start",
            "text_delta",
            "text_end",
            "thinking_start",
            "thinking_delta",
            "thinking_end",
            "toolcall_start",
            "toolcall_delta",
            "toolcall_end",
        }:
            if event.partial:
                for_event_message = event.partial
                context.messages[-1] = for_event_message
                await maybe_await(
                    emit(
                        AgentEvent(
                            type="message_update",
                            message=for_event_message,
                            assistant_message_event=event,
                        )
                    )
                )
    final = await response.result()
    if partial_added:
        context.messages[-1] = final
    else:
        context.messages.append(final)
        await maybe_await(emit(AgentEvent(type="message_start", message=final)))
    await maybe_await(emit(AgentEvent(type="message_end", message=final)))
    return final


async def _execute_tool_calls(
    current: AgentContext,
    assistant: AssistantMessage,
    tool_calls: list[ToolCall],
    config: AgentLoopConfig,
    emit: AgentEventSink,
) -> tuple[list[ToolResultMessage], bool]:
    sequential = config.tool_execution == "sequential" or any(
        _find_tool(current.tools, call.name).execution_mode == "sequential"
        for call in tool_calls
        if _find_tool(current.tools, call.name)
    )
    if sequential:
        finalized = []
        for call in tool_calls:
            finalized.append(await _execute_one_tool_call(current, assistant, call, config, emit))
    else:
        finalized = await asyncio.gather(
            *[_execute_one_tool_call(current, assistant, call, config, emit) for call in tool_calls]
        )
    messages = [_tool_result_message(call, result, is_error) for call, result, is_error in finalized]
    for message in messages:
        await maybe_await(emit(AgentEvent(type="message_start", message=message)))
        await maybe_await(emit(AgentEvent(type="message_end", message=message)))
    terminate = bool(finalized) and all(result.terminate for _, result, _ in finalized)
    return messages, terminate


async def _execute_one_tool_call(
    current: AgentContext,
    assistant: AssistantMessage,
    call: ToolCall,
    config: AgentLoopConfig,
    emit: AgentEventSink,
) -> tuple[ToolCall, AgentToolResult, bool]:
    await maybe_await(
        emit(
            AgentEvent(
                type="tool_execution_start",
                tool_call_id=call.id,
                tool_name=call.name,
                args=call.arguments,
            )
        )
    )
    tool = _find_tool(current.tools, call.name)
    if tool is None:
        result = _error_tool_result(f"Tool {call.name} not found")
        await _emit_tool_end(call, result, True, emit)
        return call, result, True
    try:
        args = tool.prepare_arguments(call.arguments) if tool.prepare_arguments else call.arguments
        validate(instance=args, schema=tool.parameters)
        if config.before_tool_call:
            before = await config.before_tool_call(
                BeforeToolCallContext(
                    assistant_message=assistant, tool_call=call, args=args, context=current
                )
            )
            if before and before.block:
                result = _error_tool_result(before.reason or "Tool execution was blocked")
                await _emit_tool_end(call, result, True, emit)
                return call, result, True

        def on_update(partial: AgentToolResult) -> None:
            asyncio.create_task(
                maybe_await(
                    emit(
                        AgentEvent(
                            type="tool_execution_update",
                            tool_call_id=call.id,
                            tool_name=call.name,
                            args=call.arguments,
                            partial_result=partial,
                        )
                    )
                )
            )

        result = await tool.execute(call.id, args, on_update)
        is_error = False
    except (ValidationError, Exception) as exc:
        result = _error_tool_result(str(exc))
        is_error = True

    if config.after_tool_call:
        try:
            after = await config.after_tool_call(
                AfterToolCallContext(
                    assistant_message=assistant,
                    tool_call=call,
                    args=call.arguments,
                    context=current,
                    result=result,
                    is_error=is_error,
                )
            )
            if after:
                result = AgentToolResult(
                    content=after.content if after.content is not None else result.content,
                    details=after.details if after.details is not None else result.details,
                    terminate=after.terminate if after.terminate is not None else result.terminate,
                )
                is_error = after.is_error if after.is_error is not None else is_error
        except Exception as exc:
            result = _error_tool_result(str(exc))
            is_error = True
    await _emit_tool_end(call, result, is_error, emit)
    return call, result, is_error


def _find_tool(tools: list[AgentTool], name: str) -> AgentTool | None:
    return next((tool for tool in tools if tool.name == name), None)


def _error_tool_result(message: str) -> AgentToolResult:
    return AgentToolResult(content=[TextContent(text=message)], details={})


async def _emit_tool_end(
    call: ToolCall, result: AgentToolResult, is_error: bool, emit: AgentEventSink
) -> None:
    await maybe_await(
        emit(
            AgentEvent(
                type="tool_execution_end",
                tool_call_id=call.id,
                tool_name=call.name,
                result=result,
                is_error=is_error,
            )
        )
    )


def _tool_result_message(call: ToolCall, result: AgentToolResult, is_error: bool) -> ToolResultMessage:
    return ToolResultMessage(
        tool_call_id=call.id,
        tool_name=call.name,
        content=result.content,
        details=result.details,
        is_error=is_error,
        timestamp=now_ms(),
    )
