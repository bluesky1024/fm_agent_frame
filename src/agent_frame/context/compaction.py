"""压缩策略适配：让运行时通过 Memory 协议触发摘要滑窗。

只有实现了 ``compact`` / ``view`` 的记忆（如 SummaryBufferMemory）才会压缩；
普通会话记忆保持原样。
"""

from __future__ import annotations

from typing import Protocol

from agent_frame.core.messages import Message


class Compactor(Protocol):
    async def compact(self, session_id: str, *, token_threshold: int, keep_last: int) -> bool: ...


class HistoryView(Protocol):
    async def view(self, session_id: str) -> list[Message]: ...


async def compact_if_needed(
    memory: object,
    session_id: str,
    *,
    token_threshold: int,
    keep_last: int,
) -> bool:
    compact = getattr(memory, "compact", None)
    if compact is None:
        return False
    return bool(await compact(session_id, token_threshold=token_threshold, keep_last=keep_last))


async def history_view(memory: object, session_id: str) -> list[Message] | None:
    """若记忆提供 view，则返回压缩后的请求视图；否则返回 None。"""
    view = getattr(memory, "view", None)
    if view is None:
        return None
    result: list[Message] = await view(session_id)
    return result
