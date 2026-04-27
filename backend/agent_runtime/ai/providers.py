from __future__ import annotations

import asyncio
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
    StreamOptions,
    TextContent,
    ToolCall,
    ToolSpec,
    Usage,
    UserMessage,
)


def now_ms() -> int:
    return int(time.time() * 1000)


def _message_text(message: Message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.text for part in content if isinstance(part, TextContent))
    return ""


class CompletedAssistantStream(AsyncEventStream[AssistantStreamEvent, AssistantMessage]):
    pass


def _start_background(coro: Any) -> CompletedAssistantStream:
    stream = CompletedAssistantStream()
    asyncio.create_task(coro(stream))
    return stream


def faux_stream(model: Model, context: Context, options: StreamOptions) -> CompletedAssistantStream:
    async def run(stream: CompletedAssistantStream) -> None:
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

    return _start_background(run)


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
            content=[TextContent(text="")],
            api=model.api,
            provider=model.provider,
            model=model.id,
            timestamp=now_ms(),
        )
        stream.push(AssistantStreamEvent(type="start", partial=partial))
        stream.push(AssistantStreamEvent(type="text_start", content_index=0, partial=partial))
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
        headers = {"Authorization": f"Bearer {options.api_key}", **model.headers, **options.headers}
        final_tool_calls: dict[int, dict[str, Any]] = {}
        try:
            async with httpx.AsyncClient(timeout=(options.timeout_ms or 600000) / 1000) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        choice = chunk.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        if text := delta.get("content"):
                            current = partial.content[0]
                            partial.content[0] = TextContent(text=current.text + text)  # type: ignore[union-attr]
                            stream.push(
                                AssistantStreamEvent(
                                    type="text_delta", content_index=0, delta=text, partial=partial
                                )
                            )
                        for tool_delta in delta.get("tool_calls") or []:
                            index = tool_delta.get("index", 0)
                            entry = final_tool_calls.setdefault(
                                index,
                                {"id": tool_delta.get("id"), "name": "", "arguments": ""},
                            )
                            if tool_delta.get("id"):
                                entry["id"] = tool_delta["id"]
                            fn = tool_delta.get("function") or {}
                            entry["name"] += fn.get("name") or ""
                            entry["arguments"] += fn.get("arguments") or ""
            text_content = partial.content[0].text if partial.content else ""
            if text_content:
                stream.push(
                    AssistantStreamEvent(
                        type="text_end", content_index=0, content=text_content, partial=partial
                    )
                )
            if final_tool_calls:
                partial.content = [
                    ToolCall(
                        id=value["id"] or f"call_{index}",
                        name=value["name"],
                        arguments=json.loads(value["arguments"] or "{}"),
                    )
                    for index, value in sorted(final_tool_calls.items())
                ]
                partial.stop_reason = "toolUse"
            stream.push(AssistantStreamEvent(type="done", reason=partial.stop_reason, message=partial))
            stream.end(partial)
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

    return _start_background(run)


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

    return _start_background(run)


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
