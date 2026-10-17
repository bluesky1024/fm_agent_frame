"""票 07：事件追踪、token/耗时统计与批量评测。"""

import json

from agent_frame.core.messages import ToolCall
from agent_frame.core.types import TokenUsage
from agent_frame.eval import AgentEvalSuite, EvalCase, ExactMatchEvaluator, RegexMatchEvaluator
from agent_frame.interfaces.session import InMemorySession
from agent_frame.llm.base import ChatResult, StreamChunk
from agent_frame.obs import ConsoleTracer, JSONLTracer, TokenTracker
from agent_frame.runtime import AgentRuntime, AgentSpec
from agent_frame.tools.builtin import CalculatorTool


class ScriptedLLM:
    def __init__(self, results: list[ChatResult]) -> None:
        self._results = list(results)

    async def chat(self, messages, tools=None) -> ChatResult:
        raise AssertionError("runtime 应使用 stream()")

    async def stream(self, messages, tools=None):
        result = self._results.pop(0)
        if result.content:
            for char in result.content:
                yield StreamChunk(text_delta=char)
        yield StreamChunk(result=result)


def _spec(llm: ScriptedLLM, **overrides) -> AgentSpec:
    values = {"llm": llm, "name": "obs-agent", "max_steps": 3}
    values.update(overrides)
    return AgentSpec(**values)


async def test_jsonl_tracer_writes_readable_trace_file(tmp_path) -> None:
    tracer = JSONLTracer(tmp_path / "trace.jsonl")
    llm = ScriptedLLM(
        [
            ChatResult(
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={"expression": "2+2"})]
            ),
            ChatResult(content="答案是 4", usage=TokenUsage(total_tokens=9)),
        ]
    )

    await AgentRuntime().run_collect(
        _spec(llm, tools=[CalculatorTool()], tracers=[tracer]),
        InMemorySession(id="s1"),
        "2+2",
    )

    lines = (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    types = [event["type"] for event in events]

    assert types[0] == "run_start"
    assert types[-1] == "run_end"
    assert "tool_result" in types
    assert events[-1]["result"]["output"] == "答案是 4"


async def test_console_tracer_prints_run_summary(capsys) -> None:
    tracer = ConsoleTracer()
    llm = ScriptedLLM([ChatResult(content="hi")])

    await AgentRuntime().run_collect(
        _spec(llm, tracers=[tracer]), InMemorySession(id="s1"), "hello"
    )

    output = capsys.readouterr().out
    assert "运行开始" in output
    assert "运行结束" in output
    assert "hi" in output


async def test_token_tracker_reports_usage_per_run_and_step() -> None:
    tracker = TokenTracker()
    llm = ScriptedLLM(
        [
            ChatResult(
                tool_calls=[ToolCall(id="c1", name="calculator", arguments={"expression": "2+2"})],
                usage=TokenUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5),
            ),
            ChatResult(
                content="4",
                usage=TokenUsage(prompt_tokens=4, completion_tokens=1, total_tokens=5),
            ),
        ]
    )

    await AgentRuntime().run_collect(
        _spec(llm, tools=[CalculatorTool()], tracers=[tracker]),
        InMemorySession(id="s1"),
        "2+2",
    )

    run = tracker.latest
    assert run is not None
    assert run.usage.total_tokens == 10
    assert [step.step for step in run.steps] == [0, 1]
    assert [step.usage.total_tokens for step in run.steps] == [5, 5]
    assert all(step.duration_ms >= 0 for step in run.steps)
    assert run.tool_calls == 1


async def test_exact_and_regex_evaluators() -> None:
    case = EvalCase(case_id="1", input="2+2", expected="4")

    exact = ExactMatchEvaluator()
    assert (await exact.evaluate(case, " 4 ")).score == 1.0
    assert (await exact.evaluate(case, "四")).score == 0.0

    regex = RegexMatchEvaluator(r"\d+")
    assert (await regex.evaluate(case, "答案是 4")).score == 1.0
    assert (await regex.evaluate(case, "4")).score == 1.0
    assert (await regex.evaluate(case, "没有数字")).score == 0.0


async def test_eval_suite_runs_batch_and_returns_report() -> None:
    llm = ScriptedLLM([ChatResult(content="4"), ChatResult(content="蓝色")])
    suite = AgentEvalSuite(
        runtime=AgentRuntime(),
        spec=_spec(llm),
        evaluator=ExactMatchEvaluator(),
        session_factory=lambda case_id: InMemorySession(id=case_id),
    )

    report = await suite.run(
        [
            EvalCase(case_id="math", input="2+2", expected="4"),
            EvalCase(case_id="color", input="天空的颜色", expected="红色"),
        ]
    )

    assert [result.case.case_id for result in report.case_results] == ["math", "color"]
    assert [result.result.score for result in report.case_results] == [1.0, 0.0]
    assert report.mean_score == 0.5
    assert report.metadata["case_count"] == 2
