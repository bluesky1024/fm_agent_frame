"""最小评测器：精确匹配与正则匹配。"""

from __future__ import annotations

import re

from agent_frame.eval.base import EvalCase, EvalResult


class ExactMatchEvaluator:
    """输出与期望完全一致时得 1 分，否则 0 分。"""

    def __init__(self, *, strip: bool = True, case_sensitive: bool = True) -> None:
        self._strip = strip
        self._case_sensitive = case_sensitive

    async def evaluate(self, case: EvalCase, output: str) -> EvalResult:
        expected = case.expected or ""
        left = self._normalize(output)
        right = self._normalize(expected)
        return EvalResult(
            score=1.0 if left == right else 0.0,
            details={"expected": expected, "output": output},
        )

    def _normalize(self, text: str) -> str:
        if self._strip:
            text = text.strip()
        if not self._case_sensitive:
            text = text.casefold()
        return text


class RegexMatchEvaluator:
    """输出匹配正则时得 1 分，否则 0 分。"""

    def __init__(self, pattern: str, *, flags: int = 0) -> None:
        self._pattern = re.compile(pattern, flags)

    async def evaluate(self, case: EvalCase, output: str) -> EvalResult:
        matched = self._pattern.search(output) is not None
        return EvalResult(
            score=1.0 if matched else 0.0,
            details={"pattern": self._pattern.pattern, "output": output},
        )
