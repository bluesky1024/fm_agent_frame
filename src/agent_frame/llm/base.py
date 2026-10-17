"""LLM 供应商协议：整包调用与流式调用。

两条路径都返回同一个 ``ChatResult``：
- ``chat()`` 直接返回完整结果；
- ``stream()`` 逐段产出文本增量，最后一个 chunk 的 ``result`` 是组装好的完整结果。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from pydantic import BaseModel, Field

from agent_frame.core.messages import Message, ToolCall
from agent_frame.core.types import TokenUsage, ToolSpec

__all__ = ["ChatResult", "LLMProvider", "StreamChunk", "ToolSpec"]


class ChatResult(BaseModel):
    """一次 LLM 调用的结果：要么是纯文本，要么是一次/多次工具调用。"""

    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class StreamChunk(BaseModel):
    """流式调用的一个片段。

    ``text_delta`` 非空时是文本增量；``result`` 非空时表示流结束，
    携带拼接完成的完整 ``ChatResult``。
    """

    text_delta: str = ""
    result: ChatResult | None = None


class LLMProvider(Protocol):
    """LLM 服务提供者协议。任何实现只需满足这个接口即可被 Agent 使用。"""

    async def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
        *,
        model: str | None = None,
    ) -> ChatResult: ...

    def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
        *,
        model: str | None = None,
    ) -> AsyncIterator[StreamChunk]: ...
