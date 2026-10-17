"""AgentSpec：无状态、可复用的 Agent 定义。

运行时循环完全由 ``AgentRuntime`` 实现；spec 只描述「用哪个模型、什么提示词、
哪些工具与扩展」，可被多个 Session 同时复用。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from agent_frame.context.providers import ContextProvider
from agent_frame.llm.base import LLMProvider
from agent_frame.memory.base import Memory
from agent_frame.obs.tracer import Tracer
from agent_frame.runtime.policies import ApprovalPolicy, Guardrail, Middleware
from agent_frame.tools.base import Tool, ToolProvider, ToolSandbox


@dataclass(frozen=True)
class AgentSpec:
    """一个 Agent 的完整数据声明。"""

    llm: LLMProvider
    name: str = "agent"
    model: str | None = None
    system_prompt: str | None = None
    tools: Sequence[Tool] = ()
    context_providers: Sequence[ContextProvider] = ()
    memory: Memory | None = None
    max_steps: int = 8
    tool_timeout: float | None = 30.0
    # 上下文 token 预算与摘要滑窗保留的最近消息数（仅对 SummaryBufferMemory 生效）
    context_token_budget: int = 4000
    compaction_keep_last: int = 6
    middleware: Sequence[Middleware] = ()
    input_guards: Sequence[Guardrail] = ()
    output_guards: Sequence[Guardrail] = ()
    approval: ApprovalPolicy | None = None
    tool_providers: Sequence[ToolProvider] = ()
    sandbox: ToolSandbox | None = None
    tracers: Sequence[Tracer] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
