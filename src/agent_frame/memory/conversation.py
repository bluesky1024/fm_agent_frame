"""短时记忆：进程内字典保存各会话的完整消息历史。"""

from __future__ import annotations

from collections.abc import Sequence

from agent_frame.messages import Message


class ConversationMemory:
    """最简单的 Memory 实现，仅存内存、不做持久化与裁剪。"""

    def __init__(self) -> None:
        self._store: dict[str, list[Message]] = {}

    async def load(self, session_id: str) -> list[Message]:
        return list(self._store.get(session_id, []))

    async def save(self, session_id: str, messages: Sequence[Message]) -> None:
        self._store[session_id] = list(messages)
