"""Agent 抽象：Agent 协议 + 运行结果与步骤记录。"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from agent_frame.memory.base import Memory


class AgentStep(BaseModel):
    """Agent 循环中的一步：这一轮 LLM 返回了什么、执行了哪些工具。"""

    index: int
    content: str | None = None
    tool_calls: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    """Agent 运行结束的结果。"""

    output: str
    steps: list[AgentStep] = Field(default_factory=list)


class Agent(Protocol):
    """Agent 协议：接收一个任务，返回最终回答。"""

    async def run(
        self,
        task: str,
        *,
        memory: Memory | None = None,
        session_id: str = "default",
    ) -> AgentResult: ...
