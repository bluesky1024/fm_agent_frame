"""示例共用：把运行时事件打印到终端，便于观察完整执行过程。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from agent_frame.core.events import (
    AgentEvent,
    ContextBuilt,
    Error,
    LLMCompleted,
    LLMDelta,
    RunEnd,
    RunStart,
    StepStart,
    ToolCallRequested,
    ToolResult,
)
from agent_frame.core.types import AgentResult
from agent_frame.runtime import AgentRuntime, AgentSpec, Session


def render_event(event: AgentEvent) -> None:
    if isinstance(event, RunStart):
        print(f"\n==> 运行开始 run={event.run_id} session={event.session_id}")
    elif isinstance(event, StepStart):
        print(f"\n[步骤 {event.step}]")
    elif isinstance(event, ContextBuilt):
        print(f"  [上下文] {event.message_count} 条消息，约 {event.token_estimate} tokens")
    elif isinstance(event, LLMDelta):
        print(event.text, end="", flush=True)
    elif isinstance(event, LLMCompleted):
        print()
    elif isinstance(event, ToolCallRequested):
        args = json.dumps(event.tool_call.arguments, ensure_ascii=False)
        print(f"  [工具请求] {event.tool_call.name}({args})")
    elif isinstance(event, ToolResult):
        if event.error:
            print(f"  [工具失败] {event.name}: {event.error}")
        else:
            print(f"  [工具结果] {event.name}: {event.content}")
    elif isinstance(event, Error):
        print(f"  [错误] {event.error}（recoverable={event.recoverable}）")
    elif isinstance(event, RunEnd):
        print(
            f"\n==> 运行结束：steps={event.result.steps}，tokens={event.result.usage.total_tokens}"
        )


async def run_and_print(
    runtime: AgentRuntime,
    spec: AgentSpec,
    session: Session,
    user_input: str,
) -> AgentResult:
    """执行一轮并打印每个事件，返回结构化结果。"""
    result = AgentResult(output="")
    async for event in _iter_events(runtime, spec, session, user_input):
        render_event(event)
        if isinstance(event, RunEnd):
            result = event.result
    return result


async def _iter_events(
    runtime: AgentRuntime,
    spec: AgentSpec,
    session: Session,
    user_input: str,
) -> AsyncIterator[AgentEvent]:
    async for event in runtime.run(spec, session, user_input):
        yield event
