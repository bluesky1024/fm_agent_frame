"""票 08：顺序编排、护栏、审批、MCP provider 与 no-op 沙箱接线。"""

from typing import Any

from agent_frame.capabilities.guardrails import KeywordGuardrail, NoopGuardrail
from agent_frame.capabilities.hitl import AutoApprove, ConsoleApprove
from agent_frame.capabilities.mcp import MCPToolProvider
from agent_frame.capabilities.multi_agent import (
    AgentRunner,
    SequentialOrchestrator,
    SubTask,
)
from agent_frame.capabilities.sandbox import NoopToolSandbox
from agent_frame.core.events import AgentEvent, Error, RunEnd, ToolResult
from agent_frame.core.messages import Message, ToolCall
from agent_frame.core.types import ToolSpec
from agent_frame.interfaces.session import InMemorySession
from agent_frame.llm.base import ChatResult, StreamChunk
from agent_frame.runtime import AgentRuntime, AgentSpec
from agent_frame.runtime.policies import ApprovalDecision
from agent_frame.tools.builtin import CalculatorTool


class ScriptedLLM:
    def __init__(self, results: list[ChatResult]) -> None:
        self._results = list(results)
        self.requests: list[list[Message]] = []

    async def chat(self, messages, tools=None) -> ChatResult:
        raise AssertionError("runtime 应使用 stream()")

    async def stream(self, messages, tools=None):
        self.requests.append(list(messages))
        result = self._results.pop(0)
        yield StreamChunk(result=result)


def _spec(llm: Any, **overrides: Any) -> AgentSpec:
    values: dict[str, Any] = {"llm": llm, "name": "ext-agent", "max_steps": 3}
    values.update(overrides)
    return AgentSpec(**values)


async def _collect(runtime: AgentRuntime, spec: AgentSpec, session, user_input: str) -> list:
    return [event async for event in runtime.run(spec, session, user_input)]


def _calculator_call(call_id: str = "c1") -> ChatResult:
    return ChatResult(
        tool_calls=[ToolCall(id=call_id, name="calculator", arguments={"expression": "2+2"})]
    )


async def test_sequential_orchestrator_runs_two_agents_in_order() -> None:
    writer_llm = ScriptedLLM([ChatResult(content="草稿")])
    reviewer_llm = ScriptedLLM([ChatResult(content="审阅意见")])
    orchestrator = SequentialOrchestrator(
        {
            "writer": AgentRunner(
                runtime=AgentRuntime(),
                spec=_spec(writer_llm, name="writer"),
                session_factory=lambda sid: InMemorySession(id=sid),
            ),
            "reviewer": AgentRunner(
                runtime=AgentRuntime(),
                spec=_spec(reviewer_llm, name="reviewer"),
                session_factory=lambda sid: InMemorySession(id=sid),
            ),
        }
    )

    result = await orchestrator.run_tasks(
        [
            SubTask(subtask_id="t1", description="写一段草稿", assignee="writer"),
            SubTask(subtask_id="t2", description="审阅草稿", assignee="reviewer"),
        ]
    )

    assert result.output == "草稿\n审阅意见"
    assert [trace.agent for trace in result.traces] == ["writer", "reviewer"]
    assert [trace.input for trace in result.traces] == ["写一段草稿", "审阅草稿"]


async def test_input_guardrail_blocks_before_llm() -> None:
    llm = ScriptedLLM([])
    session = InMemorySession(id="s1")
    spec = _spec(llm, input_guards=[KeywordGuardrail(["违规"])])

    events = await _collect(AgentRuntime(), spec, session, "这是违规内容")

    error = next(e for e in events if isinstance(e, Error))
    assert "输入被护栏拦截" in error.error
    assert isinstance(events[-1], RunEnd)
    assert llm.requests == []


async def test_output_guardrail_blocks_and_does_not_persist_assistant() -> None:
    llm = ScriptedLLM([ChatResult(content="敏感内容")])
    session = InMemorySession(id="s1")
    spec = _spec(llm, output_guards=[KeywordGuardrail(["敏感"])])

    events = await _collect(AgentRuntime(), spec, session, "正常问题")

    error = next(e for e in events if isinstance(e, Error))
    assert "输出被护栏拦截" in error.error
    assert [m.role for m in session.history] == ["user"]


async def test_noop_guardrails_keep_default_behavior() -> None:
    llm = ScriptedLLM([ChatResult(content="正常回答")])
    session = InMemorySession(id="s1")
    spec = _spec(llm, input_guards=[NoopGuardrail()], output_guards=[NoopGuardrail()])

    result = await AgentRuntime().run_collect(spec, session, "你好")

    assert result.output == "正常回答"


async def test_auto_approve_executes_tool_and_records_status() -> None:
    llm = ScriptedLLM([_calculator_call(), ChatResult(content="答案是 4")])
    approval = AutoApprove()
    session = InMemorySession(id="s1")
    spec = _spec(llm, tools=[CalculatorTool()], approval=approval)

    result = await AgentRuntime().run_collect(spec, session, "2+2")

    assert result.output == "答案是 4"
    record = approval.status("c1")
    assert record is not None and record.approved is True
    assert any(m.role == "tool" and m.content == "4" for m in session.history)


class RejectAll:
    async def approve(self, call, *, context) -> ApprovalDecision:
        return ApprovalDecision(approved=False, reason="测试拒绝")


async def test_rejected_tool_call_returns_recoverable_result() -> None:
    llm = ScriptedLLM([_calculator_call(), ChatResult(content="好的，不执行")])
    session = InMemorySession(id="s1")
    spec = _spec(llm, tools=[CalculatorTool()], approval=RejectAll())

    events = await _collect(AgentRuntime(), spec, session, "2+2")

    tool_event = next(e for e in events if isinstance(e, ToolResult))
    assert tool_event.error is not None and "拒绝" in tool_event.error
    assert not any(isinstance(e, Error) for e in events)
    assert any("拒绝" in (m.content or "") for m in session.history if m.role == "tool")


async def test_console_approve_uses_injected_ask_and_records_status() -> None:
    llm = ScriptedLLM([_calculator_call(), ChatResult(content="换个方式")])
    approval = ConsoleApprove(ask=lambda call: False)
    session = InMemorySession(id="s1")
    spec = _spec(llm, tools=[CalculatorTool()], approval=approval)

    await AgentRuntime().run_collect(spec, session, "2+2")

    record = approval.status("c1")
    assert record is not None and record.approved is False


class FakeMCPClient:
    async def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="remote_add",
                description="远程加法",
                parameters={
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"],
                },
            )
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        return str(arguments["a"] + arguments["b"])


async def test_mcp_provider_is_wired_into_tool_execution() -> None:
    llm = ScriptedLLM(
        [
            ChatResult(
                tool_calls=[ToolCall(id="m1", name="remote_add", arguments={"a": 2, "b": 3})]
            ),
            ChatResult(content="等于 5"),
        ]
    )
    session = InMemorySession(id="s1")
    spec = _spec(llm, tool_providers=[MCPToolProvider(FakeMCPClient())])

    await AgentRuntime().run_collect(spec, session, "2+3")

    assert any(m.role == "tool" and m.content == "5" for m in session.history)


async def test_noop_sandbox_is_wired_into_execution() -> None:
    llm = ScriptedLLM([_calculator_call(), ChatResult(content="4")])
    session = InMemorySession(id="s1")
    spec = _spec(llm, tools=[CalculatorTool()], sandbox=NoopToolSandbox())

    events: list[AgentEvent] = await _collect(AgentRuntime(), spec, session, "2+2")

    tool_event = next(e for e in events if isinstance(e, ToolResult))
    assert tool_event.content == "4"
