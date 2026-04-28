from __future__ import annotations

from agent_runtime.agent import Agent
from agent_runtime.agent.loop import run_agent_loop
from agent_runtime.agent.types import (
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    AgentTool,
    AgentToolResult,
    AfterToolCallResult,
    CustomAgentMessage,
)
from agent_runtime.ai.event_stream import AsyncEventStream
from agent_runtime.ai.providers import openai_completions_stream
from agent_runtime.ai.types import (
    AssistantMessage,
    AssistantStreamEvent,
    Context,
    Model,
    StreamOptions,
    TextContent,
    ToolCall,
    UserMessage,
)
from agent_runtime.tools import default_tools


def faux_model() -> Model:
    return Model(id="faux-tool-model", name="Faux", api="faux", provider="faux")


async def test_agent_loop_streams_plain_assistant_message() -> None:
    events: list[AgentEvent] = []
    prompt = UserMessage(content="hello", timestamp=1)
    config = AgentLoopConfig(
        model=faux_model(),
        convert_to_llm=lambda messages: messages,
    )
    messages = await run_agent_loop(
        [prompt],
        AgentContext(system_prompt="test", tools=default_tools()),
        config,
        events.append,
    )

    assert messages[0] == prompt
    assert messages[-1].role == "assistant"
    assert any(event.type == "message_update" for event in events)
    assert events[-1].type == "agent_end"


async def test_agent_loop_executes_tool_and_continues() -> None:
    events: list[AgentEvent] = []
    prompt = UserMessage(content="please tool:echo", timestamp=1)
    config = AgentLoopConfig(
        model=faux_model(),
        convert_to_llm=lambda messages: messages,
    )
    messages = await run_agent_loop(
        [prompt],
        AgentContext(system_prompt="test", tools=default_tools()),
        config,
        events.append,
    )

    assert any(message.role == "toolResult" for message in messages)
    assert any(event.type == "tool_execution_start" for event in events)
    assert any(event.type == "tool_execution_end" and not event.is_error for event in events)


async def test_after_tool_call_can_terminate_loop() -> None:
    events: list[AgentEvent] = []
    prompt = UserMessage(content="please tool:echo", timestamp=1)

    async def after_tool_call(context):
        return AfterToolCallResult(
            content=[TextContent(text="done")],
            details={"patched": True},
            terminate=True,
        )

    config = AgentLoopConfig(
        model=faux_model(),
        convert_to_llm=lambda messages: messages,
        after_tool_call=after_tool_call,
    )
    messages = await run_agent_loop(
        [prompt],
        AgentContext(system_prompt="test", tools=default_tools()),
        config,
        events.append,
    )

    assert sum(1 for message in messages if message.role == "assistant") == 1


async def test_agent_abstraction_owns_state_and_events() -> None:
    events: list[AgentEvent] = []
    agent = Agent(model=faux_model(), system_prompt="test", tools=default_tools())
    agent.subscribe(events.append)

    stream = agent.run([UserMessage(content="hello", timestamp=1)])
    messages = await stream.result()

    assert messages[-1].role == "assistant"
    assert agent.state.messages == messages
    assert events[-1].type == "agent_end"


async def test_custom_agent_message_is_transformed_before_llm() -> None:
    notification = CustomAgentMessage(
        role="notification",
        text="UI-only notice",
        timestamp=1,
    )
    prompt = UserMessage(content="hello", timestamp=2)
    seen_roles: list[str] = []

    def convert_to_llm(messages):
        converted = []
        for message in messages:
            seen_roles.append(message.role)
            if message.role in {"user", "assistant", "toolResult"}:
                converted.append(message)
        return converted

    config = AgentLoopConfig(
        model=faux_model(),
        transform_context=lambda messages: messages,
        convert_to_llm=convert_to_llm,
    )

    messages = await run_agent_loop(
        [prompt],
        AgentContext(system_prompt="test", messages=[notification], tools=default_tools()),
        config,
        lambda event: None,
    )

    assert "notification" in seen_roles
    assert messages[0] == prompt


async def test_custom_stream_fn_gets_options_and_signal() -> None:
    seen: dict[str, object] = {}

    def stream_fn(model: Model, context: Context, options: StreamOptions):
        seen["session_id"] = options.session_id
        seen["signal"] = options.signal
        stream: AsyncEventStream[AssistantStreamEvent, AssistantMessage] = AsyncEventStream()
        message = AssistantMessage(
            content=[TextContent(text="custom")],
            api=model.api,
            provider=model.provider,
            model=model.id,
            timestamp=1,
        )
        stream.push(AssistantStreamEvent(type="start", partial=message))
        stream.push(AssistantStreamEvent(type="done", reason="stop", message=message))
        stream.end(message)
        return stream

    agent = Agent(
        model=faux_model(),
        system_prompt="test",
        stream_options=StreamOptions(session_id="session-1"),
        stream_fn=stream_fn,
    )
    stream = agent.run([UserMessage(content="hello", timestamp=1)])
    messages = await stream.result()

    assert messages[-1].content[0].text == "custom"
    assert seen["session_id"] == "session-1"
    assert seen["signal"] is not None


async def test_tool_updates_are_emitted_before_tool_end() -> None:
    events: list[AgentEvent] = []

    async def execute(tool_call_id, params, signal, on_update):
        on_update(AgentToolResult(content=[TextContent(text="working")], details={"phase": "update"}))
        return AgentToolResult(content=[TextContent(text="done")], details={"tool_call_id": tool_call_id})

    tool = AgentTool(
        name="echo",
        label="Echo",
        description="Echo",
        parameters={"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"]},
        execute=execute,
    )
    config = AgentLoopConfig(model=faux_model(), convert_to_llm=lambda messages: messages)
    await run_agent_loop(
        [UserMessage(content="please tool:echo", timestamp=1)],
        AgentContext(system_prompt="test", tools=[tool]),
        config,
        events.append,
    )

    update_index = next(i for i, event in enumerate(events) if event.type == "tool_execution_update")
    end_index = next(i for i, event in enumerate(events) if event.type == "tool_execution_end")
    assert update_index < end_index


async def test_agent_runtime_failure_settles_stream() -> None:
    agent = Agent(
        model=faux_model(),
        system_prompt="test",
        transform_context=lambda messages: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    stream = agent.run([UserMessage(content="hello", timestamp=1)])
    messages = await stream.result()

    assert messages[0].role == "assistant"
    assert messages[0].stop_reason == "error"
    assert messages[0].error_message == "boom"
    assert agent.state.is_streaming is False


async def test_openai_provider_streams_tool_call_deltas(monkeypatch) -> None:
    class FakeResponse:
        status_code = 200
        headers = {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","function":{"name":"echo","arguments":"{\\"input\\":"}}]}}]}'
            yield 'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"hello\\"}"}}]}}]}'
            yield "data: [DONE]"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("agent_runtime.ai.providers.httpx.AsyncClient", FakeClient)

    stream = openai_completions_stream(
        Model(id="gpt-test", name="GPT Test", api="openai-completions", provider="openai"),
        Context(messages=[UserMessage(content="call echo", timestamp=1)]),
        StreamOptions(api_key="test"),
    )
    events = [event async for event in stream]
    message = await stream.result()

    assert [event.type for event in events if event.type.startswith("toolcall")] == [
        "toolcall_start",
        "toolcall_delta",
        "toolcall_delta",
        "toolcall_end",
    ]
    assert isinstance(message.content[0], ToolCall)
    assert message.content[0].arguments == {"input": "hello"}
