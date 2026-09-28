"""LLM 客户端抽象：统一封装「发消息 → 得回复（可能含工具调用）」。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel

from agent_frame.messages import Message, ToolCall


class ChatResult(BaseModel):
    """一次 LLM 调用的结果：要么是纯文本，要么是一次/多次工具调用。"""

    content: str | None = None
    tool_calls: list[ToolCall] | None = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class ToolSpec(BaseModel):
    """给 LLM 描述一个可用工具（对应 OpenAI function 内层对象）。"""

    name: str
    description: str
    parameters: dict[str, Any]


class LLMProvider(Protocol):
    """LLM 服务提供者协议。任何实现只需满足这个接口即可被 Agent 使用。"""

    async def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ChatResult: ...
