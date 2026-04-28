from __future__ import annotations

import asyncio
import inspect
import json
import time
import uuid
from typing import Any

import httpx

from agent_runtime.ai.event_stream import AsyncEventStream
from agent_runtime.ai.registry import ApiProvider, register_api_provider
from agent_runtime.ai.types import (
    AssistantMessage,
    AssistantStreamEvent,
    Context,
    Message,
    Model,
    ProviderResponse,
    StreamOptions,
    TextContent,
    ToolCall,
    ToolSpec,
    Usage,
    UserMessage,
)


def now_ms() -> int:
    return int(time.time() * 1000)


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _check_aborted(options: StreamOptions) -> None:
    if options.signal is not None:
        options.signal.throw_if_aborted()


def _parse_streaming_json(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _message_text(message: Message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.text for part in content if isinstance(part, TextContent))
    return ""


class CompletedAssistantStream(AsyncEventStream[AssistantStreamEvent, AssistantMessage]):
    pass


def _start_background(coro: Any, model: Model | None = None) -> CompletedAssistantStream:
    stream = CompletedAssistantStream()

    async def run() -> None:
        try:
            await coro(stream)
        except asyncio.CancelledError as exc:
            if model is None:
                raise
            message = AssistantMessage(
                content=[TextContent(text="")],
                api=model.api,
                provider=model.provider,
                model=model.id,
                stop_reason="aborted",
                error_message=str(exc),
                timestamp=now_ms(),
            )
            stream.push(AssistantStreamEvent(type="error", reason="aborted", error=message))
            stream.end(message)
        except Exception as exc:
            if model is None:
                raise
            message = AssistantMessage(
                content=[TextContent(text=str(exc))],
                api=model.api,
                provider=model.provider,
                model=model.id,
                stop_reason="error",
                error_message=str(exc),
                timestamp=now_ms(),
            )
            stream.push(AssistantStreamEvent(type="error", reason="error", error=message))
            stream.end(message)

    asyncio.create_task(run())
    return stream


def faux_stream(model: Model, context: Context, options: StreamOptions) -> CompletedAssistantStream:
    async def run(stream: CompletedAssistantStream) -> None:
        _check_aborted(options)
        last_message = context.messages[-1] if context.messages else None
        if getattr(last_message, "role", None) == "toolResult":
            tool_text = _message_text(last_message)
            partial = AssistantMessage(
                content=[TextContent(text=f"Tool result: {tool_text}")],
                api=model.api,
                provider=model.provider,
                model=model.id,
                stop_reason="stop",
                timestamp=now_ms(),
            )
            stream.push(AssistantStreamEvent(type="start", partial=partial))
            stream.push(
                AssistantStreamEvent(
                    type="text_end", content_index=0, content=partial.content[0].text, partial=partial
                )
            )
            stream.push(AssistantStreamEvent(type="done", reason="stop", message=partial))
            stream.end(partial)
            return

        last_user = next((m for m in reversed(context.messages) if isinstance(m, UserMessage)), None)
        text = _message_text(last_user) if last_user else ""
        partial = AssistantMessage(
            content=[],
            api=model.api,
            provider=model.provider,
            model=model.id,
            stop_reason="stop",
            timestamp=now_ms(),
        )
        stream.push(AssistantStreamEvent(type="start", partial=partial))

        if context.tools and "tool:" in text:
            requested = text.split("tool:", 1)[1].strip().split()[0]
            tool_name = requested if any(tool.name == requested for tool in context.tools) else context.tools[0].name
            call = ToolCall(id=f"call_{uuid.uuid4().hex[:10]}", name=tool_name, arguments={"input": text})
            partial.content = [call]
            partial.stop_reason = "toolUse"
            stream.push(AssistantStreamEvent(type="toolcall_start", content_index=0, partial=partial))
            stream.push(
                AssistantStreamEvent(
                    type="toolcall_end", content_index=0, tool_call=call, partial=partial
                )
            )
            stream.push(AssistantStreamEvent(type="done", reason="toolUse", message=partial))
            stream.end(partial)
            return

        final_text = f"Echo: {text}" if text else "Echo"
        partial.content = [TextContent(text="")]
        stream.push(AssistantStreamEvent(type="text_start", content_index=0, partial=partial))
        for token in final_text.split(" "):
            _check_aborted(options)
            await asyncio.sleep(0)
            delta = token + " "
            partial.content[0] = TextContent(text=partial.content[0].text + delta)  # type: ignore[index]
            stream.push(
                AssistantStreamEvent(
                    type="text_delta", content_index=0, delta=delta, partial=partial
                )
            )
        final_content = partial.content[0].text.strip()  # type: ignore[index]
        partial.content[0] = TextContent(text=final_content)  # type: ignore[index]
        stream.push(
            AssistantStreamEvent(
                type="text_end", content_index=0, content=final_content, partial=partial
            )
        )
        stream.push(AssistantStreamEvent(type="done", reason="stop", message=partial))
        stream.end(partial)

    return _start_background(run, model)


def _json_schema_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def _openai_messages(context: Context) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if context.system_prompt:
        messages.append({"role": "system", "content": context.system_prompt})
    for message in context.messages:
        if message.role == "user":
            messages.append({"role": "user", "content": _message_text(message)})
        elif message.role == "assistant":
            messages.append(
                {
                    "role": "assistant",
                    "content": "\n".join(
                        part.text for part in message.content if isinstance(part, TextContent)
                    )
                    or None,
                    "tool_calls": [
                        {
                            "id": part.id,
                            "type": "function",
                            "function": {
                                "name": part.name,
                                "arguments": json.dumps(part.arguments),
                            },
                        }
                        for part in message.content
                        if isinstance(part, ToolCall)
                    ]
                    or None,
                }
            )
        elif message.role == "toolResult":
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "name": message.tool_name,
                    "content": "\n".join(part.text for part in message.content),
                }
            )
    return messages


def openai_completions_stream(model: Model, context: Context, options: StreamOptions) -> CompletedAssistantStream:
    async def run(stream: CompletedAssistantStream) -> None:
        partial = AssistantMessage(
            content=[],
            api=model.api,
            provider=model.provider,
            model=model.id,
            timestamp=now_ms(),
        )
        stream.push(AssistantStreamEvent(type="start", partial=partial))
        url = (model.base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": model.id,
            "messages": _openai_messages(context),
            "stream": True,
        }
        if context.tools:
            payload["tools"] = _json_schema_tools(context.tools)
        if options.temperature is not None:
            payload["temperature"] = options.temperature
        if options.max_tokens:
            payload["max_tokens"] = options.max_tokens
        if options.on_payload:
            replaced = await maybe_await(options.on_payload(payload, model))
            if replaced is not None:
                payload = replaced
        headers = {"Authorization": f"Bearer {options.api_key}", **model.headers, **options.headers}
        text_index: int | None = None
        tool_calls: dict[int, dict[str, Any]] = {}
        try:
            _check_aborted(options)
            async with httpx.AsyncClient(timeout=(options.timeout_ms or 600000) / 1000) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if options.on_response:
                        await maybe_await(
                            options.on_response(
                                ProviderResponse(status=response.status_code, headers=dict(response.headers)),
                                model,
                            )
                        )
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        _check_aborted(options)
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        choice = chunk.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        if text := delta.get("content"):
                            if text_index is None:
                                text_index = len(partial.content)
                                partial.content.append(TextContent(text=""))
                                stream.push(
                                    AssistantStreamEvent(
                                        type="text_start", content_index=text_index, partial=partial
                                    )
                                )
                            current = partial.content[text_index]
                            partial.content[text_index] = TextContent(
                                text=current.text + text  # type: ignore[union-attr]
                            )
                            stream.push(
                                AssistantStreamEvent(
                                    type="text_delta", content_index=text_index, delta=text, partial=partial
                                )
                            )
                        for tool_delta in delta.get("tool_calls") or []:
                            index = tool_delta.get("index", 0)
                            entry = tool_calls.get(index)
                            if entry is None:
                                content_index = len(partial.content)
                                entry = {
                                    "content_index": content_index,
                                    "id": tool_delta.get("id") or f"call_{index}",
                                    "name": "",
                                    "arguments_json": "",
                                }
                                tool_calls[index] = entry
                                partial.content.append(
                                    ToolCall(id=entry["id"], name="", arguments={})
                                )
                                stream.push(
                                    AssistantStreamEvent(
                                        type="toolcall_start",
                                        content_index=content_index,
                                        partial=partial,
                                    )
                                )
                            if tool_delta.get("id"):
                                entry["id"] = tool_delta["id"]
                            fn = tool_delta.get("function") or {}
                            entry["name"] += fn.get("name") or ""
                            args_delta = fn.get("arguments") or ""
                            entry["arguments_json"] += args_delta
                            partial.content[entry["content_index"]] = ToolCall(
                                id=entry["id"],
                                name=entry["name"],
                                arguments=_parse_streaming_json(entry["arguments_json"]),
                            )
                            if args_delta:
                                stream.push(
                                    AssistantStreamEvent(
                                        type="toolcall_delta",
                                        content_index=entry["content_index"],
                                        delta=args_delta,
                                        partial=partial,
                                    )
                                )
            if text_index is not None:
                text_content = partial.content[text_index].text  # type: ignore[union-attr]
                stream.push(
                    AssistantStreamEvent(
                        type="text_end", content_index=text_index, content=text_content, partial=partial
                    )
                )
            if tool_calls:
                for _, value in sorted(tool_calls.items()):
                    tool_call = ToolCall(
                        id=value["id"],
                        name=value["name"],
                        arguments=_parse_streaming_json(value["arguments_json"]),
                    )
                    partial.content[value["content_index"]] = tool_call
                    stream.push(
                        AssistantStreamEvent(
                            type="toolcall_end",
                            content_index=value["content_index"],
                            tool_call=tool_call,
                            partial=partial,
                        )
                    )
                partial.stop_reason = "toolUse"
            stream.push(AssistantStreamEvent(type="done", reason=partial.stop_reason, message=partial))
            stream.end(partial)
        except asyncio.CancelledError as exc:
            error = AssistantMessage(
                content=partial.content or [TextContent(text="")],
                api=model.api,
                provider=model.provider,
                model=model.id,
                stop_reason="aborted",
                error_message=str(exc),
                usage=Usage(),
                timestamp=now_ms(),
            )
            stream.push(AssistantStreamEvent(type="error", reason="aborted", error=error))
            stream.end(error)
        except Exception as exc:
            error = AssistantMessage(
                content=[TextContent(text=str(exc))],
                api=model.api,
                provider=model.provider,
                model=model.id,
                stop_reason="error",
                error_message=str(exc),
                usage=Usage(),
                timestamp=now_ms(),
            )
            stream.push(AssistantStreamEvent(type="error", reason="error", error=error))
            stream.end(error)

    return _start_background(run, model)


def unsupported_stream(model: Model, context: Context, options: StreamOptions) -> CompletedAssistantStream:
    async def run(stream: CompletedAssistantStream) -> None:
        message = AssistantMessage(
            content=[
                TextContent(
                    text=(
                        f"Provider API {model.api!r} is registered but does not yet have a "
                        "native Python streaming adapter."
                    )
                )
            ],
            api=model.api,
            provider=model.provider,
            model=model.id,
            stop_reason="error",
            error_message=f"Unsupported API adapter: {model.api}",
            timestamp=now_ms(),
        )
        stream.push(AssistantStreamEvent(type="start", partial=message))
        stream.push(AssistantStreamEvent(type="error", reason="error", error=message))
        stream.end(message)

    return _start_background(run, model)


def register_builtin_providers() -> None:
    register_api_provider(ApiProvider("faux", faux_stream))
    register_api_provider(ApiProvider("openai-completions", openai_completions_stream))
    for api in [
        "mistral-conversations",
        "openai-responses",
        "azure-openai-responses",
        "openai-codex-responses",
        "anthropic-messages",
        "bedrock-converse-stream",
        "google-generative-ai",
        "google-gemini-cli",
        "google-vertex",
    ]:
        register_api_provider(ApiProvider(api, unsupported_stream))
