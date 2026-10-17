"""核心事件：覆盖 ADR-0003 约定的九类运行事件。"""

from agent_frame.core.events import (
    AgentEvent,
    ContextBuilt,
    Error,
    LLMCompleted,
    LLMDelta,
    RunEnd,
    RunStart,
    StepStart,
    ToolCallRequested,
    ToolResult,
)
from agent_frame.core.messages import Message, ToolCall
from agent_frame.core.types import AgentResult, TokenUsage


def test_run_start_and_step_start_carry_run_identity() -> None:
    start = RunStart(run_id="r1", session_id="s1", input="你好")
    step = StepStart(step=0)

    assert start.type == "run_start"
    assert start.run_id == "r1"
    assert start.input == "你好"
    assert step.type == "step_start"
    assert step.step == 0


def test_context_and_stream_events() -> None:
    built = ContextBuilt(message_count=3, token_estimate=42)
    delta = LLMDelta(text="你")

    assert built.type == "context_built"
    assert built.message_count == 3
    assert built.token_estimate == 42
    assert delta.type == "llm_delta"
    assert delta.text == "你"


def test_llm_completed_carries_message_and_usage() -> None:
    usage = TokenUsage(prompt_tokens=3, completion_tokens=5, total_tokens=8)
    event = LLMCompleted(message=Message.assistant("你好"), usage=usage)

    assert event.type == "llm_completed"
    assert event.message.content == "你好"
    assert event.usage.total_tokens == 8


def test_tool_events() -> None:
    call = ToolCall(id="c1", name="calculator", arguments={"expression": "1+1"})
    requested = ToolCallRequested(tool_call=call)
    ok = ToolResult(tool_call_id="c1", name="calculator", content="2")
    failed = ToolResult(tool_call_id="c2", name="calculator", error="计算失败")

    assert requested.type == "tool_call_requested"
    assert requested.tool_call.name == "calculator"
    assert ok.type == "tool_result"
    assert ok.content == "2"
    assert failed.error == "计算失败"


def test_run_end_and_error_events() -> None:
    result = AgentResult(
        output="完成",
        usage=TokenUsage(total_tokens=10),
        steps=2,
    )
    end = RunEnd(result=result)
    error = Error(error="超过最大步数", recoverable=False)

    assert end.type == "run_end"
    assert end.result.output == "完成"
    assert end.result.steps == 2
    assert error.type == "error"
    assert error.recoverable is False


def test_events_are_agent_events_and_serializable() -> None:
    event = LLMDelta(text="hi")

    assert isinstance(event, AgentEvent)
    dumped = event.model_dump()
    assert dumped["type"] == "llm_delta"
    assert dumped["text"] == "hi"
