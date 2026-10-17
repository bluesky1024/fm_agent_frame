"""运行时扩展协议：中间件、护栏、审批策略。

由 ``runtime`` 定义、由 ``capabilities`` 实现（依赖倒置）。
首版在票 08 接入完整能力；本文件先固定协议形状。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent_frame.core.messages import Message, ToolCall
from agent_frame.core.types import TokenUsage
from agent_frame.llm.base import ChatResult
from agent_frame.tools.base import ToolResult


@dataclass
class RunContext:
    """钩子可见的当前运行上下文。"""

    run_id: str
    session_id: str
    spec_name: str
    step: int
    usage: TokenUsage


class Middleware(Protocol):
    """不修改循环即可插入的行为钩子；每个钩子都可改写输入或输出。"""

    async def before_llm(self, context: RunContext, messages: list[Message]) -> list[Message]: ...

    async def after_llm(self, context: RunContext, result: ChatResult) -> ChatResult: ...

    async def before_tool(self, context: RunContext, call: ToolCall) -> ToolCall: ...

    async def after_tool(self, context: RunContext, result: ToolResult) -> ToolResult: ...


class BaseMiddleware:
    """所有钩子的空实现，便于只覆写关心的部分。"""

    async def before_llm(self, context: RunContext, messages: list[Message]) -> list[Message]:
        return messages

    async def after_llm(self, context: RunContext, result: ChatResult) -> ChatResult:
        return result

    async def before_tool(self, context: RunContext, call: ToolCall) -> ToolCall:
        return call

    async def after_tool(self, context: RunContext, result: ToolResult) -> ToolResult:
        return result


@dataclass(frozen=True)
class GuardrailDecision:
    """护栏结论：允许、拒绝，或替换文本。"""

    allowed: bool = True
    reason: str | None = None
    replacement: str | None = None


class Guardrail(Protocol):
    """输入/输出内容检查，可短路本次运行。"""

    async def check(self, text: str, *, context: RunContext) -> GuardrailDecision: ...


@dataclass(frozen=True)
class ApprovalDecision:
    """工具调用审批结论。"""

    approved: bool
    reason: str | None = None


class ApprovalPolicy(Protocol):
    """工具执行前审批（human-in-the-loop）。"""

    async def approve(self, call: ToolCall, *, context: RunContext) -> ApprovalDecision: ...
