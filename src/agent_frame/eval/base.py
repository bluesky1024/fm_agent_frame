"""评测抽象：用例、评测器、套件与报告。

评测要回答：这个 Agent 的输出质量到底如何？核心能力：
- 用一批「用例」定义输入与期望答案
- 用「评测器」给单条输出打分（规则匹配 / LLM-as-judge / 检索指标等）
- 用「套件」跑完整批用例，产出「报告」用于对比

本文件只定义接口（Protocol + 数据模型），不提供具体实现。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel, Field


# ---------- 数据模型 ----------


class EvalCase(BaseModel):
    """一条评测用例。"""

    case_id: str
    input: str
    expected: str | None = None  # 期望答案（可选，取决于评测方式）
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    """单条用例的评测结果。"""

    score: float  # 分数（0~1 或任意，取决于评测器约定）
    details: dict[str, Any] = Field(default_factory=dict)


class CaseResult(BaseModel):
    """单条用例 + 其评测结果。"""

    case: EvalCase
    result: EvalResult


class EvalReport(BaseModel):
    """一次评测的汇总报告。"""

    case_results: list[CaseResult] = Field(default_factory=list)
    mean_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------- 协议 ----------


class Evaluator(Protocol):
    """评测器：给一条用例的输出打分。"""

    async def evaluate(self, case: EvalCase, output: str) -> EvalResult: ...


class EvalSuite(Protocol):
    """评测套件：对一批用例运行被测对象并评分，产出报告。

    实现通常内部持有被测对象（agent 或可调用对象）与 Evaluator。
    """

    async def run(self, cases: Sequence[EvalCase]) -> EvalReport: ...
