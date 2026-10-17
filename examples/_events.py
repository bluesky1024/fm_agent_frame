"""示例共用：把运行时事件交给 ConsoleTracer 打印，并返回结构化结果。"""

from __future__ import annotations

from agent_frame.core.events import AgentEvent, RunEnd
from agent_frame.core.types import AgentResult
from agent_frame.obs import ConsoleTracer
from agent_frame.runtime import AgentRuntime, AgentSpec, Session

_console = ConsoleTracer()


def render_event(event: AgentEvent) -> None:
    _console.on_event(event)


async def run_and_print(
    runtime: AgentRuntime,
    spec: AgentSpec,
    session: Session,
    user_input: str,
) -> AgentResult:
    """执行一轮并打印每个事件，返回结构化结果。"""
    result = AgentResult(output="")
    async for event in runtime.run(spec, session, user_input):
        render_event(event)
        if isinstance(event, RunEnd):
            result = event.result
    return result
