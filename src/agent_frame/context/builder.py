"""每轮请求视图装配：system + 前置片段 + 压缩后的历史 + 后置片段。

提供者默认插入历史之前；声明 ``placement = "after_history"`` 的提供者
（如视觉观察帧）追加在历史之后，成为模型看到的最新消息。
装配结果只用于本次 LLM 调用，不写回 Session 历史（ADR-0004）。
历史视图由记忆层提供（可能是「摘要 + 滑动窗口」）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

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
        before_history: list[Message] = []
        after_history: list[Message] = []
        for provider in self._providers:
            provided = await provider.provide(request)
            target = (
                after_history
                if getattr(provider, "placement", "before_history") == "after_history"
                else before_history
            )
            target.extend(provided)

        messages.extend(before_history)
        messages.extend(history)
        messages.extend(after_history)
        return BuiltContext(messages=messages, token_estimate=estimate_tokens(messages))
