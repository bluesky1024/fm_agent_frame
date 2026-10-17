"""输入/输出护栏：空实现与关键词拦截示例，真实接入 runtime。"""

from __future__ import annotations

from collections.abc import Sequence

from agent_frame.runtime.policies import GuardrailDecision, RunContext


class NoopGuardrail:
    """默认护栏：永远放行，不改变主流程行为。"""

    async def check(self, text: str, *, context: RunContext) -> GuardrailDecision:
        return GuardrailDecision(allowed=True)


class KeywordGuardrail:
    """命中任意关键词即拒绝，并给出可读原因。"""

    def __init__(self, blocked_words: Sequence[str], *, reason: str | None = None) -> None:
        self._blocked = [word for word in blocked_words if word]
        self._reason = reason or "内容包含被禁止的关键词"

    async def check(self, text: str, *, context: RunContext) -> GuardrailDecision:
        for word in self._blocked:
            if word in text:
                return GuardrailDecision(allowed=False, reason=f"{self._reason}: {word}")
        return GuardrailDecision(allowed=True)
