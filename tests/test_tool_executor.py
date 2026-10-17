"""工具执行器：schema 校验、并行、超时、错误分类与 provider 接线。"""

import asyncio
from typing import Any, ClassVar

import pytest

from agent_frame.core.errors import ToolError
from agent_frame.core.messages import ToolCall
from agent_frame.core.types import ToolSpec
from agent_frame.tools import ToolExecutor, ToolRegistry


class EchoTool:
    name: ClassVar[str] = "echo"
    description: ClassVar[str] = "回显文本"
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def __init__(self) -> None:
        self.calls = 0

    async def run(self, text: str) -> str:
        self.calls += 1
        return text


def _call(name: str, arguments: dict[str, Any], call_id: str = "c1") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=arguments)


async def test_invalid_arguments_return_structured_error_without_executing() -> None:
    tool = EchoTool()
    executor = ToolExecutor(ToolRegistry([tool]))

    result = await executor.execute(_call("echo", {}))

    assert result.ok is False
    assert result.error_type == "validation"
    assert result.recoverable is True
    assert "text" in (result.error or "")
    assert tool.calls == 0


async def test_valid_arguments_execute_tool() -> None:
    tool = EchoTool()
    executor = ToolExecutor(ToolRegistry([tool]))

    result = await executor.execute(_call("echo", {"text": "你好"}))

    assert result.ok is True
    assert result.content == "你好"
    assert result.tool_call_id == "c1"
    assert result.name == "echo"


async def test_unknown_tool_is_recoverable_error() -> None:
    executor = ToolExecutor(ToolRegistry([EchoTool()]))

    result = await executor.execute(_call("missing", {}))

    assert result.ok is False
    assert result.error_type == "unknown_tool"
    assert result.recoverable is True


async def test_batch_tools_run_in_parallel() -> None:
    barrier = asyncio.Barrier(2)

    class BarrierTool:
        name: ClassVar[str] = "barrier"
        description: ClassVar[str] = "等待另一批调用同时到达"
        parameters: ClassVar[dict[str, Any]] = {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        }

        async def run(self, key: str) -> str:
            await barrier.wait()
            return key

    executor = ToolExecutor(ToolRegistry([BarrierTool()]), timeout=1.0)

    results = await asyncio.wait_for(
        executor.execute_many(
            [_call("barrier", {"key": "a"}, "1"), _call("barrier", {"key": "b"}, "2")]
        ),
        timeout=0.5,
    )

    assert [r.content for r in results] == ["a", "b"]


async def test_single_call_timeout_returns_recoverable_error() -> None:
    class SlowTool:
        name: ClassVar[str] = "slow"
        description: ClassVar[str] = "慢工具"
        parameters: ClassVar[dict[str, Any]] = {
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
            "required": ["seconds"],
        }

        async def run(self, seconds: float) -> str:
            await asyncio.sleep(seconds)
            return "done"

    executor = ToolExecutor(ToolRegistry([SlowTool()]), timeout=0.01)

    result = await executor.execute(_call("slow", {"seconds": 1}))

    assert result.ok is False
    assert result.error_type == "timeout"
    assert result.recoverable is True


async def test_recoverable_tool_error_becomes_result() -> None:
    class RecoverableTool:
        name: ClassVar[str] = "recoverable"
        description: ClassVar[str] = "可恢复失败"
        parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

        async def run(self) -> str:
            raise ToolError("参数暂时不可用", recoverable=True)

    executor = ToolExecutor(ToolRegistry([RecoverableTool()]))

    result = await executor.execute(_call("recoverable", {}))

    assert result.ok is False
    assert result.error == "参数暂时不可用"
    assert result.recoverable is True


async def test_fatal_tool_error_propagates() -> None:
    class FatalTool:
        name: ClassVar[str] = "fatal"
        description: ClassVar[str] = "致命失败"
        parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

        async def run(self) -> str:
            raise ToolError("无法恢复", recoverable=False)

    executor = ToolExecutor(ToolRegistry([FatalTool()]))

    with pytest.raises(ToolError):
        await executor.execute(_call("fatal", {}))


async def test_unexpected_exception_is_recoverable_by_default() -> None:
    class ExplodingTool:
        name: ClassVar[str] = "explode"
        description: ClassVar[str] = "抛异常"
        parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

        async def run(self) -> str:
            raise RuntimeError("boom")

    executor = ToolExecutor(ToolRegistry([ExplodingTool()]))

    result = await executor.execute(_call("explode", {}))

    assert result.ok is False
    assert result.error == "boom"
    assert result.recoverable is True


class EchoProvider:
    async def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(name="remote_echo", description="远程回显", parameters=EchoTool.parameters)
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        return f"remote:{arguments['text']}"


async def test_provider_tools_are_listed_and_executed() -> None:
    executor = ToolExecutor(ToolRegistry(), providers=[EchoProvider()])

    specs = await executor.tool_specs()
    result = await executor.execute(_call("remote_echo", {"text": "hello"}))

    assert [s.name for s in specs] == ["remote_echo"]
    assert result.content == "remote:hello"
    assert result.ok is True


async def test_provider_tools_are_validated() -> None:
    executor = ToolExecutor(ToolRegistry(), providers=[EchoProvider()])

    result = await executor.execute(_call("remote_echo", {}))

    assert result.error_type == "validation"
    assert result.ok is False


class RecordingSandbox:
    def __init__(self) -> None:
        self.names: list[str] = []

    async def execute(self, tool: Any, arguments: dict[str, Any]) -> str:
        self.names.append(tool.name)
        return await tool.run(**arguments)


async def test_sandbox_wraps_local_tool_execution() -> None:
    sandbox = RecordingSandbox()
    executor = ToolExecutor(ToolRegistry([EchoTool()]), sandbox=sandbox)

    result = await executor.execute(_call("echo", {"text": "沙箱"}))

    assert result.content == "沙箱"
    assert sandbox.names == ["echo"]
