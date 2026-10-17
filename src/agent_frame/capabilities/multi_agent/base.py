"""多 Agent 协作协议：拆任务、顺序/并行编排与交接。"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class SubAgentSpec(BaseModel):
    """一个子 Agent 的角色描述（不持有运行时对象）。"""

    name: str
    description: str
    system_prompt: str
    tools: list[str] = Field(default_factory=list)
    model: str | None = None


class SubTask(BaseModel):
    """编排中拆分出的一个子任务。"""

    subtask_id: str
    description: str
    assignee: str | None = None
    dependencies: list[str] = Field(default_factory=list)


class AgentTrace(BaseModel):
    """某个子 agent 的一次执行记录。"""

    agent: str
    input: str
    output: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestrationResult(BaseModel):
    """多 Agent 编排的最终结果。"""

    output: str
    traces: list[AgentTrace] = Field(default_factory=list)


class TaskDecomposer(Protocol):
    """任务拆分：把一个总任务拆成若干子任务。"""

    async def decompose(self, task: str) -> list[SubTask]: ...


class AgentOrchestrator(Protocol):
    """顺序编排：拆任务 → 分发到子 Agent → 汇总结果。"""

    async def run(self, task: str, decomposer: TaskDecomposer) -> OrchestrationResult: ...


class ParallelOrchestrator(Protocol):
    """并行编排扩展点：首版只保留协议。"""

    async def run_parallel(self, tasks: list[SubTask]) -> OrchestrationResult: ...


class AgentHandoff(Protocol):
    """Agent 交接扩展点：首版只保留协议。"""

    async def handoff(self, *, from_agent: str, to_agent: str, reason: str) -> SubTask | None: ...
