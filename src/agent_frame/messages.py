"""消息模型：与 OpenAI 兼容协议对齐的消息结构。

DeepSeek 走 OpenAI 兼容协议，一条消息用 role + 可选字段表达：
- system / user：纯文本（content: str）或图文混合（content: list[TextPart|ImagePart]）
- assistant：可能是纯文本（content），也可能是一次工具调用（tool_calls）
- tool：对某次 tool_call 的返回，用 tool_call_id 关联到对应调用
"""

from __future__ import annotations

import base64
from typing import Any, Literal

from pydantic import BaseModel, Field


class TextPart(BaseModel):
    """多模态消息里的文本片段。"""

    type: Literal["text"] = "text"
    text: str


class ImagePart(BaseModel):
    """多模态消息里的图片片段（image_url 内放 data URL 或 http URL）。"""

    type: Literal["image_url"] = "image_url"
    image_url: dict[str, str]


ContentPart = TextPart | ImagePart


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
    content: str | list[ContentPart] | None = None
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
    def user_with_image(
        cls, text: str, png: bytes, *, detail: str = "high"
    ) -> "Message":
        """构造一条「文本 + 内联 PNG 图片」的 user 消息（base64 data URL）。"""
        data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        return cls(
            role="user",
            content=[
                TextPart(text=text),
                ImagePart(image_url={"url": data_url, "detail": detail}),
            ],
        )

    @classmethod
    def assistant(
        cls, content: str | None = None, tool_calls: list[ToolCall] | None = None
    ) -> "Message":
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, tool_call_id: str, content: str, name: str | None = None) -> "Message":
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)
