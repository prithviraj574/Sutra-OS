from __future__ import annotations

import time
from typing import Any

from agent_runtime.agent.types import AgentTool, AgentToolResult, ToolUpdateCallback
from agent_runtime.ai.types import TextContent


async def echo_execute(
    tool_call_id: str, params: dict[str, Any], on_update: ToolUpdateCallback | None = None
) -> AgentToolResult:
    text = str(params.get("input", ""))
    if on_update:
        on_update(AgentToolResult(content=[TextContent(text="echo started")], details={"phase": "start"}))
    return AgentToolResult(content=[TextContent(text=text)], details={"tool_call_id": tool_call_id})


async def current_time_execute(
    tool_call_id: str, params: dict[str, Any], on_update: ToolUpdateCallback | None = None
) -> AgentToolResult:
    return AgentToolResult(
        content=[TextContent(text=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))],
        details={"tool_call_id": tool_call_id, "timezone": "UTC"},
    )


def default_tools() -> list[AgentTool]:
    return [
        AgentTool(
            name="echo",
            label="Echo",
            description="Return the provided input text.",
            parameters={
                "type": "object",
                "properties": {"input": {"type": "string"}},
                "required": ["input"],
            },
            execute=echo_execute,
        ),
        AgentTool(
            name="current_time",
            label="Current time",
            description="Return the current UTC time.",
            parameters={"type": "object", "properties": {}},
            execute=current_time_execute,
        ),
    ]
