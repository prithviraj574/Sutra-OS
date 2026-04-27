from __future__ import annotations

from agent_runtime.agent import Agent
from agent_runtime.agent.loop import run_agent_loop
from agent_runtime.agent.types import AgentContext, AgentEvent, AgentLoopConfig, AfterToolCallResult
from agent_runtime.ai.types import Model, TextContent, UserMessage
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
