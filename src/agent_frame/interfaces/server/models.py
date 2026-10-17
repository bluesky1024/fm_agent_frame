"""HTTP 服务的请求/响应模型与结构化错误。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """一次聊天请求。"""

    message: str = Field(min_length=1, description="用户输入")
    session_id: str | None = Field(default=None, description="会话 ID；不传则新建会话")
    stream: bool = Field(default=True, description="是否以 SSE 流式返回事件")

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message 不能为空")
        return value


class ChatResponse(BaseModel):
    """非流式响应。"""

    reply: str
    session_id: str
    usage: dict[str, Any] | None = None


class ErrorDetail(BaseModel):
    type: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class InvalidRequestError(ValueError):
    """服务层直接调用时的非法输入。"""
