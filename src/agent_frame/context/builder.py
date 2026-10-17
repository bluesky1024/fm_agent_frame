"""每轮请求视图装配：system + 提供者片段 + 持久历史。

装配结果只用于本次 LLM 调用，不写回 Session 历史（ADR-0004）。
首版实现不做压缩；token 预算与摘要压缩在票 06 接入。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from agent_frame.context.providers import ContextProvider, ContextRequest
from agent_frame.core.messages import Message


@dataclass(frozen=True)
class BuiltContext:
    """一次装配结果：发给 LLM 的消息视图与粗略 token 估算。"""

    messages: list[Message]
    token_estimate: int


class ContextBuilder:
    """把 system prompt、上下文提供者片段与持久历史拼成请求视图。"""

    def __init__(self, providers: Sequence[ContextProvider] = ()) -> None:
        self._providers = list(providers)

    async def build(
        self,
        *,
        system_prompt: str | None,
        history: Sequence[Message],
        user_input: str,
        session_id: str,
    ) -> BuiltContext:
        messages: list[Message] = []
        if system_prompt:
            messages.append(Message.system(system_prompt))

        request = ContextRequest(
            session_id=session_id,
            input=user_input,
            history=list(history),
        )
        for provider in self._providers:
            messages.extend(await provider.provide(request))

        messages.extend(history)
        return BuiltContext(messages=messages, token_estimate=estimate_tokens(messages))


def estimate_tokens(messages: Sequence[Message]) -> int:
    """粗略估算 token：按字符数 / 4，只用于事件与调试。"""
    chars = 0
    for message in messages:
        if isinstance(message.content, str):
            chars += len(message.content)
        elif message.content is not None:
            chars += sum(len(str(part)) for part in message.content)
        if message.tool_calls:
            chars += sum(len(str(call)) for call in message.tool_calls)
    return max(1, chars // 4)


@dataclass
class MutableContextState:
    """预留：供票 06 的压缩策略暂存每会话状态。"""

    extra: dict[str, str] = field(default_factory=dict)
