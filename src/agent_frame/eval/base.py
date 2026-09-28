"""评测抽象（打桩）。

后续学习如何衡量 Agent 输出质量：用 LLM 打分、规则校验、对比基准等。
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class EvalResult(BaseModel):
    """一次评测的结果。"""

    score: float
    details: dict[str, Any] = Field(default_factory=dict)


class Evaluator(Protocol):
    async def evaluate(
        self, task: str, output: str, expected: str | None = None
    ) -> EvalResult: ...
