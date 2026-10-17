"""AgentRuntime 主接缝（S1）：事件序列、工具循环、步数、取消与中间件。"""

import asyncio
from typing import Any

import pytest

from agent_frame.core.events import (
    AgentEvent,
    ContextBuilt,
    Error,
    LLMCompleted,
    LLMDelta,
    RunEnd,
    RunStart,
    ToolResult,
)
from agent_frame.core.messages import Message, ToolCall
from agent_frame.core.types import TokenUsage
from agent_frame.interfaces.session import InMemorySession
from agent_frame.llm.base import ChatResult, StreamChunk
from agent_frame.runtime import AgentRuntime
from agent_frame.runtime.policies import BaseMiddleware
from agent_frame.runtime.spec import AgentSpec
from agent_frame.tools.builtin import CalculatorTool


class ScriptedLLM:
    """按脚本返回响应；记录每次收到的 messages。"""

    def __init__(self, results: list[ChatResult]) -> None:
        self._results = list(results)
        self.requests: list[list[Message]] = []
        self.models: list[str | None] = []

    async def chat(self, messages, tools=None, *, model=None) -> ChatResult:
        raise AssertionError("runtime 应使用 stream()")

    async def stream(self, messages, tools=None, *, model=None):
        self.requests.append(list(messages))
        self.models.append(model)
        result = self._results.pop(0)
        if result.content:
            for char in result.content:
                yield StreamChunk(text_delta=char)
        yield StreamChunk(result=result)


def _spec(llm: Any, **overrides: Any) -> AgentSpec:
    values: dict[str, Any] = {
        "llm": llm,
        "name": "calculator-agent",
        "system_prompt": "你是一个计算助手。",
        "tools": [CalculatorTool()],
        "max_steps": 5,
    }
    values.update(overrides)
    return AgentSpec(**values)


def _types(events: list[AgentEvent]) -> list[str]:
    return [event.type for event in events]


async def _collect(runtime: AgentRuntime, spec: AgentSpec, session, user_input: str) -> list:
    return [event async for event in runtime.run(spec, session, user_input)]


def _tool_call_result() -> ChatResult:
    return ChatResult(
        content="我来算一下",
        tool_calls=[ToolCall(id="c1", name="calculator", arguments={"expression": "2+2"})],
        usage=TokenUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5),
    )


async def test_tool_loop_event_sequence_and_history() -> None:
    llm = ScriptedLLM(
        [
            _tool_call_result(),
            ChatResult(content="答案是 4", usage=TokenUsage(total_tokens=7)),
        ]
    )
    runtime = AgentRuntime()
    session = InMemorySession(id="s1")
    spec = _spec(llm)

    events = await _collect(runtime, spec, session, "2 加 2 是多少？")

    assert _types(events) == [
        "run_start",
        "step_start",
        "context_built",
        *(["llm_delta"] * 5),  # “我来算一下”
        "llm_completed",
        "tool_call_requested",
        "tool_result",
        "step_start",
        "context_built",
        *(["llm_delta"] * 5),  # “答案是 4”
        "llm_completed",
        "run_end",
    ]

    started = events[0]
    assert isinstance(started, RunStart)
    assert started.session_id == "s1"
    assert started.input == "2 加 2 是多少？"

    tool_event = next(e for e in events if isinstance(e, ToolResult))
    assert tool_event.content == "4"

    end = events[-1]
    assert isinstance(end, RunEnd)
    assert end.result.output == "答案是 4"
    assert end.result.steps == 2
    assert end.result.usage.total_tokens == 12

    # 历史中没有 system 消息；工具轮的 assistant 文本被保留
    roles = [m.role for m in session.history]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert session.history[1].content == "我来算一下"
    assert session.history[1].tool_calls is not None
    assert session.history[2].content == "4"
    assert session.history[3].content == "答案是 4"
    assert session.last_run is not None
    assert session.last_run.output == "答案是 4"


async def test_context_is_assembled_per_step_without_writing_system_to_history() -> None:
    llm = ScriptedLLM(
        [
            _tool_call_result(),
            ChatResult(content="完成"),
        ]
    )
    runtime = AgentRuntime()
    session = InMemorySession(id="s1")
    spec = _spec(llm)

    await _collect(runtime, spec, session, "算一下")

    assert len(llm.requests) == 2
    for request in llm.requests:
        assert request[0].role == "system"
        assert request[0].content == "你是一个计算助手。"
        assert sum(1 for m in request if m.role == "system") == 1
    assert all(m.role != "system" for m in session.history)


async def test_context_builder_event_reports_message_count() -> None:
    llm = ScriptedLLM([ChatResult(content="ok")])
    runtime = AgentRuntime()
    session = InMemorySession(id="s1")

    events = await _collect(runtime, _spec(llm), session, "你好")

    built = next(e for e in events if isinstance(e, ContextBuilt))
    # system + user
    assert built.message_count == 2
    assert built.token_estimate > 0


async def test_max_steps_emits_error_and_run_end() -> None:
    llm = ScriptedLLM(
        [
            _tool_call_result(),
            _tool_call_result(),
            _tool_call_result(),
        ]
    )
    runtime = AgentRuntime()
    session = InMemorySession(id="s1")
    spec = _spec(llm, max_steps=2)

    events = await _collect(runtime, spec, session, "无限算下去")

    error = next(e for e in events if isinstance(e, Error))
    assert "最大步数" in error.error
    assert error.recoverable is False
    end = events[-1]
    assert isinstance(end, RunEnd)
    assert end.result.steps == 2


async def test_stream_deltas_are_emitted_before_completion() -> None:
    llm = ScriptedLLM([ChatResult(content="你好呀")])
    runtime = AgentRuntime()
    session = InMemorySession(id="s1")

    events = await _collect(runtime, _spec(llm), session, "hi")

    deltas = [e.text for e in events if isinstance(e, LLMDelta)]
    assert "".join(deltas) == "你好呀"
    completed = next(e for e in events if isinstance(e, LLMCompleted))
    assert completed.message.content == "你好呀"


async def test_spec_model_is_forwarded_to_provider() -> None:
    llm = ScriptedLLM([ChatResult(content="ok")])
    runtime = AgentRuntime()
    session = InMemorySession(id="s1")
    spec = _spec(llm, model="custom-model")

    await _collect(runtime, spec, session, "hi")

    assert llm.models == ["custom-model"]


async def test_run_collect_returns_structured_result() -> None:
    llm = ScriptedLLM([ChatResult(content="答案", usage=TokenUsage(total_tokens=9))])
    runtime = AgentRuntime()
    session = InMemorySession(id="s1")

    result = await runtime.run_collect(_spec(llm), session, "问题")

    assert result.output == "答案"
    assert result.steps == 1
    assert result.usage.total_tokens == 9


class RecordingMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def before_llm(self, context, messages):
        self.calls.append(("before_llm", context.step))
        return messages

    async def after_llm(self, context, result):
        self.calls.append(("after_llm", context.step))
        return result

    async def before_tool(self, context, call):
        self.calls.append(("before_tool", context.step))
        return call

    async def after_tool(self, context, result):
        self.calls.append(("after_tool", context.step))
        return result


async def test_middleware_hooks_are_invoked() -> None:
    llm = ScriptedLLM([_tool_call_result(), ChatResult(content="完成")])
    middleware = RecordingMiddleware()
    runtime = AgentRuntime()
    session = InMemorySession(id="s1")
    spec = _spec(llm, middleware=[middleware])

    await _collect(runtime, spec, session, "算一下")

    assert middleware.calls == [
        ("before_llm", 0),
        ("after_llm", 0),
        ("before_tool", 0),
        ("after_tool", 0),
        ("before_llm", 1),
        ("after_llm", 1),
    ]


class NamedMiddleware(BaseMiddleware):
    def __init__(self, name: str, log: list[str]) -> None:
        self._name = name
        self._log = log

    async def before_llm(self, context, messages):
        self._log.append(f"{self._name}:before_llm")
        return messages

    async def after_llm(self, context, result):
        self._log.append(f"{self._name}:after_llm")
        return result

    async def before_tool(self, context, call):
        self._log.append(f"{self._name}:before_tool")
        return call

    async def after_tool(self, context, result):
        self._log.append(f"{self._name}:after_tool")
        return result


async def test_after_middleware_runs_in_reverse_order() -> None:
    log: list[str] = []
    llm = ScriptedLLM([_tool_call_result(), ChatResult(content="完成")])
    spec = _spec(
        llm,
        middleware=[NamedMiddleware("one", log), NamedMiddleware("two", log)],
    )

    await _collect(AgentRuntime(), spec, InMemorySession(id="s1"), "算一下")

    assert log == [
        "one:before_llm",
        "two:before_llm",
        "two:after_llm",
        "one:after_llm",
        "one:before_tool",
        "two:before_tool",
        "two:after_tool",
        "one:after_tool",
        "one:before_llm",
        "two:before_llm",
        "two:after_llm",
        "one:after_llm",
    ]


class BlockingLLM:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def chat(self, messages, tools=None, *, model=None) -> ChatResult:
        raise AssertionError("runtime 应使用 stream()")

    async def stream(self, messages, tools=None, *, model=None):
        self.started.set()
        await asyncio.Event().wait()
        yield StreamChunk(result=ChatResult(content="不会到达"))


async def test_cancellation_emits_error_and_run_end() -> None:
    llm = BlockingLLM()
    runtime = AgentRuntime()
    session = InMemorySession(id="s1")
    events: list[AgentEvent] = []

    async def consume() -> None:
        async for event in runtime.run(_spec(llm), session, "hi"):
            events.append(event)

    task = asyncio.create_task(consume())
    await asyncio.wait_for(llm.started.wait(), timeout=1.0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert any(isinstance(e, Error) and "取消" in e.error for e in events)
    assert isinstance(events[-1], RunEnd)


async def test_fatal_tool_error_leaves_valid_tool_history() -> None:
    from agent_frame.core.errors import ToolError

    class FatalTool:
        name = "fatal"
        description = "致命失败"
        parameters: dict[str, Any] = {"type": "object", "properties": {}}

        async def run(self) -> str:
            raise ToolError("无法恢复", recoverable=False)

    llm = ScriptedLLM([ChatResult(tool_calls=[ToolCall(id="c1", name="fatal", arguments={})])])
    session = InMemorySession(id="s1")
    spec = _spec(llm, tools=[FatalTool()])

    events = await _collect(AgentRuntime(), spec, session, "试试")

    assert any(isinstance(e, Error) for e in events)
    assert isinstance(events[-1], RunEnd)
    assert [m.role for m in session.history] == ["user", "assistant", "tool"]
    assert session.history[1].tool_calls is not None
    assert session.history[2].tool_call_id == "c1"
    assert "无法恢复" in (session.history[2].content or "")


async def test_tool_failure_is_written_to_history() -> None:
    class BrokenTool:
        name = "broken"
        description = "总是失败"
        parameters: dict[str, Any] = {"type": "object", "properties": {}}

        async def run(self) -> str:
            raise RuntimeError("磁盘不可用")

    llm = ScriptedLLM(
        [
            ChatResult(tool_calls=[ToolCall(id="c1", name="broken", arguments={})]),
            ChatResult(content="收到，我换个办法"),
        ]
    )
    runtime = AgentRuntime()
    session = InMemorySession(id="s1")
    spec = _spec(llm, tools=[BrokenTool()])

    events = await _collect(runtime, spec, session, "试试")

    failed = next(e for e in events if isinstance(e, ToolResult))
    assert failed.error == "磁盘不可用"
    assert session.history[2].role == "tool"
    assert "磁盘不可用" in (session.history[2].content or "")
