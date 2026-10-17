"""评测套件：消费运行时事件流跑批并产出结构化报告。"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from agent_frame.core.events import RunEnd
from agent_frame.eval.base import CaseResult, EvalCase, EvalReport, Evaluator
from agent_frame.runtime.runtime import AgentRuntime
from agent_frame.runtime.session import Session
from agent_frame.runtime.spec import AgentSpec


class AgentEvalSuite:
    """对一批用例运行同一个 runtime/spec，并用评测器打分。"""

    def __init__(
        self,
        runtime: AgentRuntime,
        spec: AgentSpec,
        evaluator: Evaluator,
        session_factory: Callable[[str], Session],
    ) -> None:
        self._runtime = runtime
        self._spec = spec
        self._evaluator = evaluator
        self._session_factory = session_factory

    async def run(self, cases: Sequence[EvalCase]) -> EvalReport:
        results: list[CaseResult] = []
        for case in cases:
            session = self._session_factory(case.case_id)
            output = await self._run_case(session, case.input)
            evaluation = await self._evaluator.evaluate(case, output)
            results.append(CaseResult(case=case, result=evaluation))

        mean_score = (
            sum(result.result.score for result in results) / len(results) if results else 0.0
        )
        return EvalReport(
            case_results=results,
            mean_score=mean_score,
            metadata={"case_count": len(results), "spec": self._spec.name},
        )

    async def _run_case(self, session: Session, user_input: str) -> str:
        output = ""
        async for event in self._runtime.run(self._spec, session, user_input):
            if isinstance(event, RunEnd):
                output = event.result.output
        return output
