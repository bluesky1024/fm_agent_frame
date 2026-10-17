"""粗略 token 估算：按字符数 / 4，只用于预算与调试，不追求精确。"""

from __future__ import annotations

from collections.abc import Sequence

from agent_frame.core.messages import Message


def estimate_tokens(messages: Sequence[Message]) -> int:
    """估算一组消息的 token 数（中文按字符、工具调用按字符串长度折算）。"""
    chars = 0
    for message in messages:
        if isinstance(message.content, str):
            chars += len(message.content)
        elif message.content is not None:
            chars += sum(len(str(part)) for part in message.content)
        if message.tool_calls:
            chars += sum(len(str(call)) for call in message.tool_calls)
    return max(1, chars // 4)
