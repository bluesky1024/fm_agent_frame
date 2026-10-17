"""上下文提供者协议：记忆召回、检索、画像等按需贡献请求视图片段。

``context`` 层位于 ``runtime`` 之下，不能引用 Session，因此用
``ContextRequest`` 传递运行时需要的只读快照。
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from agent_frame.core.messages import Message


class ContextRequest(BaseModel):
    """一次上下文装配请求。"""

    session_id: str
    input: str
    history: list[Message] = Field(default_factory=list)


class ContextProvider(Protocol):
    """为一个请求视图贡献额外的消息片段（按提供者顺序插入历史之前）。"""

    async def provide(self, request: ContextRequest) -> list[Message]: ...
