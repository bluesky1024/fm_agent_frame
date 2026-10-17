"""顺序编排器：把子任务依次交给各自的 runtime/spec 执行并汇总。"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from agent_frame.capabilities.multi_agent.base import (
    AgentTrace,
    OrchestrationResult,
    SubTask,
    TaskDecomposer,
)
from agent_frame.runtime.runtime import AgentRuntime
from agent_frame.runtime.session import Session
from agent_frame.runtime.spec import AgentSpec


@dataclass
class AgentRunner:
    """一个子 Agent 的运行时组合。"""

    runtime: AgentRuntime
    spec: AgentSpec
    session_factory: Callable[[str], Session]


class SequentialOrchestrator:
    """按 SubTask 顺序执行，首个失败即中断，最终拼接各子结果。"""

    def __init__(self, agents: Mapping[str, AgentRunner]) -> None:
        self._agents = dict(agents)

    async def run(self, task: str, decomposer: TaskDecomposer) -> OrchestrationResult:
        return await self.run_tasks(await decomposer.decompose(task))

    async def run_tasks(self, tasks: Sequence[SubTask]) -> OrchestrationResult:
        traces: list[AgentTrace] = []
        for task in tasks:
            if not task.assignee:
                raise ValueError(f"子任务 {task.subtask_id} 缺少 assignee")
            runner = self._agents.get(task.assignee)
            if runner is None:
                raise ValueError(f"未注册的子 Agent: {task.assignee}")
            session = runner.session_factory(f"{task.subtask_id}:{task.assignee}")
            result = await runner.runtime.run_collect(runner.spec, session, task.description)
            traces.append(
                AgentTrace(
                    agent=task.assignee,
                    input=task.description,
                    output=result.output,
                )
            )
        return OrchestrationResult(
            output="\n".join(trace.output for trace in traces),
            traces=traces,
        )
