"""消息模型：与 OpenAI 兼容协议对齐的消息结构。

DeepSeek 走 OpenAI 兼容协议，一条消息用 role + 可选字段表达：
- system / user：纯文本，用 content
- assistant：可能是纯文本（content），也可能是一次工具调用（tool_calls）
- tool：对某次 tool_call 的返回，用 tool_call_id 关联到对应调用
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """助手发起的一次工具调用。

    arguments 是「已解析」的 dict（内部使用），
    与 OpenAI 线上协议的 JSON 字符串格式的转换见 llm/openai_compat.py。
    """

    id: str = Field(description="本次调用的唯一 ID，tool 消息据此回填结果")
    name: str = Field(description="工具名")
    arguments: dict[str, Any] = Field(default_factory=dict, description="已解析的参数")


class Message(BaseModel):
    """一条对话消息。"""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    # ---- 便捷构造 ----
    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role="user", content=content)

    @classmethod
    def assistant(
        cls, content: str | None = None, tool_calls: list[ToolCall] | None = None
    ) -> "Message":
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, tool_call_id: str, content: str, name: str | None = None) -> "Message":
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)
