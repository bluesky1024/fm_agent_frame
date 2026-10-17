"""HTTP 服务抽象：把 Agent 暴露为服务的能力面。

核心能力：
- 同步对话 / 流式输出
- 会话管理（把多轮对话串成一个 session）

本文件只定义接口（Protocol + 数据模型），不提供具体实现。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from pydantic import BaseModel, Field

# ---------- 数据模型 ----------


class ChatRequest(BaseModel):
    """一次对话请求。"""

    message: str
    session_id: str | None = None
    stream: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """一次对话响应。"""

    reply: str
    session_id: str
    usage: dict[str, Any] | None = None  # token 用量等


class SessionInfo(BaseModel):
    """会话元信息。"""

    session_id: str
    created_at: float
    message_count: int = 0


# ---------- 协议 ----------


class AgentService(Protocol):
    """把 Agent 暴露为服务的接口。"""

    async def chat(self, request: ChatRequest) -> ChatResponse: ...

    def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """流式输出，逐段产出文本。"""
        ...


class SessionManager(Protocol):
    """会话管理：创建、查询、删除会话。"""

    async def create(self) -> str:
        """创建会话，返回 session_id。"""
        ...

    async def get(self, session_id: str) -> SessionInfo: ...

    async def delete(self, session_id: str) -> None: ...
