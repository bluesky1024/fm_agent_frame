"""多 Agent 编排抽象：定义子 Agent、拆任务、编排与汇总。

业界常见的多 Agent 协作模式（顺序、并行、路由、群组对话）都建立在
「拆任务 → 分发 → 汇总」这条主线上。

本文件只定义接口（Protocol + 数据模型），不提供具体实现。
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

# ---------- 数据模型 ----------


class AgentSpec(BaseModel):
    """定义一个子 Agent 的规格（角色描述）。"""

    name: str
    description: str
    system_prompt: str
    tools: list[str] = Field(default_factory=list)  # 可用工具名（解耦，不直接引用 Tool 对象）
    model: str | None = None


class SubTask(BaseModel):
    """编排中拆分出的一个子任务。"""

    subtask_id: str
    description: str
    assignee: str | None = None  # 交给哪个 agent（名字）
    dependencies: list[str] = Field(default_factory=list)  # 依赖的子任务 id


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


# ---------- 协议 ----------


class TaskDecomposer(Protocol):
    """任务拆分：把一个总任务拆成若干子任务（可能是规则或 LLM 驱动）。"""

    async def decompose(self, task: str) -> list[SubTask]: ...


class AgentOrchestrator(Protocol):
    """多 Agent 编排：拆任务 → 分发到子 Agent → 汇总结果。"""

    async def run(self, task: str) -> OrchestrationResult: ...
