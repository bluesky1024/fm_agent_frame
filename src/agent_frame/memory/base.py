"""记忆抽象：加载 / 保存对话历史。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from agent_frame.messages import Message


class Memory(Protocol):
    """记忆协议。session_id 用于区分不同会话。"""

    async def load(self, session_id: str) -> list[Message]: ...

    async def save(self, session_id: str, messages: Sequence[Message]) -> None: ...
