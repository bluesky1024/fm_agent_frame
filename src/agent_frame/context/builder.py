"""每轮请求视图装配：system + 提供者片段 + 压缩后的历史。

装配结果只用于本次 LLM 调用，不写回 Session 历史（ADR-0004）。
历史视图由记忆层提供（可能是「摘要 + 滑动窗口」）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from agent_frame.context.providers import ContextProvider, ContextRequest
from agent_frame.core.messages import Message
from agent_frame.core.tokens import estimate_tokens


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


@dataclass
class MutableContextState:
    """预留：供票 06 的压缩策略暂存每会话状态。"""

    extra: dict[str, str] = field(default_factory=dict)
