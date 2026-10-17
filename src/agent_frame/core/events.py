"""运行事件：AgentRuntime 事件流的全部事件类型（ADR-0003）。

每个事件带 ``type`` 字符串字段，便于序列化到 SSE / JSONL trace；
事件只依赖 core 内的模型，保证最底层不反向依赖运行时。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agent_frame.core.messages import Message, ToolCall
from agent_frame.core.types import AgentResult, TokenUsage


class AgentEvent(BaseModel):
    """所有运行事件的基类。"""

    type: str


class RunStart(AgentEvent):
    """一次运行开始。"""

    type: Literal["run_start"] = "run_start"
    run_id: str
    session_id: str
    input: str


class StepStart(AgentEvent):
    """一步（一次 LLM 调用及其后的工具执行）开始。"""

    type: Literal["step_start"] = "step_start"
    step: int


class ContextBuilt(AgentEvent):
    """本轮请求视图装配完成。"""

    type: Literal["context_built"] = "context_built"
    message_count: int
    token_estimate: int


class LLMDelta(AgentEvent):
    """LLM 流式输出的一个文本增量。"""

    type: Literal["llm_delta"] = "llm_delta"
    text: str


class LLMCompleted(AgentEvent):
    """LLM 一次调用完成，携带完整消息与用量。"""

    type: Literal["llm_completed"] = "llm_completed"
    message: Message
    usage: TokenUsage = Field(default_factory=TokenUsage)


class ToolCallRequested(AgentEvent):
    """运行时请求执行一次工具调用。"""

    type: Literal["tool_call_requested"] = "tool_call_requested"
    tool_call: ToolCall


class ToolResult(AgentEvent):
    """一次工具调用的结果（成功时 content，失败时 error）。"""

    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    name: str
    content: str | None = None
    error: str | None = None


class RunEnd(AgentEvent):
    """一次运行结束。"""

    type: Literal["run_end"] = "run_end"
    result: AgentResult


class Error(AgentEvent):
    """运行中的错误；recoverable=False 表示本次运行已终止。"""

    type: Literal["error"] = "error"
    error: str
    recoverable: bool = False
