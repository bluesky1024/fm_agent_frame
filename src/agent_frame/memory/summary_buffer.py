"""摘要 + 滑动窗口记忆。

- 原始历史完整保存在内存中（``load`` / ``save``）；
- 超过阈值时把最旧的一段折叠成摘要（``compact``）；
- 请求视图由 ``view`` 给出：摘要消息 + 尚未折叠的最近消息。

摘要与滑动窗口只影响「发给模型看什么」，不会改写原始历史，
因此装配结果不会被重复持久化（ADR-0004）。
"""

from __future__ import annotations

from collections.abc import Sequence

from agent_frame.core.messages import Message
from agent_frame.core.tokens import estimate_tokens
from agent_frame.memory.base import Summarizer


class TruncatingSummarizer:
    """确定性摘要器：把一段消息拼成简短文本，用于本地测试与无 LLM 场景。"""

    def __init__(self, max_chars: int = 400) -> None:
        self._max_chars = max_chars

    async def summarize(self, messages: Sequence[Message]) -> str:
        parts = []
        for message in messages:
            text = _text_of(message)
            if text:
                parts.append(f"{message.role}: {text}")
        joined = "；".join(parts)
        if len(joined) > self._max_chars:
            return joined[: self._max_chars] + "…"
        return joined


class SummaryBufferMemory:
    """满足 Memory 协议，并额外提供 view / compact。"""

    def __init__(self, summarizer: Summarizer | None = None) -> None:
        self._summarizer = summarizer or TruncatingSummarizer()
        self._store: dict[str, list[Message]] = {}
        self._summaries: dict[str, str] = {}
        self._summarized: dict[str, int] = {}

    async def load(self, session_id: str) -> list[Message]:
        return list(self._store.get(session_id, []))

    async def save(self, session_id: str, messages: Sequence[Message]) -> None:
        self._store[session_id] = list(messages)

    async def view(self, session_id: str) -> list[Message]:
        """返回请求视图：已有摘要时放在最前，其余是未折叠的最近消息。"""
        history = self._store.get(session_id, [])
        summary = self._summaries.get(session_id)
        summarized = self._summarized.get(session_id, 0)
        messages: list[Message] = []
        if summary:
            messages.append(Message.system(f"此前对话摘要：{summary}"))
        messages.extend(history[summarized:])
        return messages

    async def compact(
        self,
        session_id: str,
        *,
        token_threshold: int,
        keep_last: int,
    ) -> bool:
        """超过阈值时把较旧的消息折叠进摘要；返回是否发生压缩。"""
        history = self._store.get(session_id, [])
        start = self._summarized.get(session_id, 0)
        pending = history[start:]
        if estimate_tokens(pending) <= token_threshold:
            return False

        cut = _safe_cut(pending, keep_last)
        if cut <= 0:
            return False

        new_summary = await self._summarizer.summarize(pending[:cut])
        existing = self._summaries.get(session_id)
        self._summaries[session_id] = (
            f"{existing}\n{new_summary}" if existing and new_summary else existing or new_summary
        )
        self._summarized[session_id] = start + cut
        return True

    async def summary(self, session_id: str) -> str | None:
        return self._summaries.get(session_id)


def _safe_cut(pending: Sequence[Message], keep_last: int) -> int:
    """选一个不切断 assistant(tool_calls)+tool 序列的切点。"""
    if len(pending) <= keep_last:
        return 0
    target = len(pending) - keep_last
    for index in range(target, 0, -1):
        if pending[index].role == "user":
            return index
    return target


def _text_of(message: Message) -> str:
    if isinstance(message.content, str):
        return message.content
    if message.tool_calls:
        return "调用工具 " + ", ".join(call.name for call in message.tool_calls)
    return ""
