"""工具执行器：参数校验、同批并行、超时与错误分类。

执行规则（architecture.md §6）：
- 参数不符合 JSON Schema：返回结构化错误，且**不执行**工具；
- 同一批调用并行执行，单次调用受 timeout 限制；
- 可恢复错误作为 ToolResult 返回；``ToolError(recoverable=False)`` 向上抛出；
- 注册表工具可经 ToolSandbox 包装；动态 provider 工具走 provider.call。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from agent_frame.core.errors import ToolError
from agent_frame.core.messages import ToolCall
from agent_frame.core.types import ToolSpec
from agent_frame.tools.base import Tool, ToolProvider, ToolResult, ToolSandbox
from agent_frame.tools.registry import ToolRegistry


class ToolExecutor:
    """统一执行入口：校验 → 并行 → 超时 → 错误分类。"""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        providers: Sequence[ToolProvider] = (),
        timeout: float | None = 30.0,
        sandbox: ToolSandbox | None = None,
    ) -> None:
        self._registry = registry or ToolRegistry()
        self._providers = list(providers)
        self._timeout = timeout
        self._sandbox = sandbox

    async def tool_specs(self) -> list[ToolSpec]:
        """导出注册表与动态 provider 的全部工具描述。"""
        specs = self._registry.to_tool_specs()
        for provider in self._providers:
            specs.extend(await provider.list_tools())
        return specs

    async def execute(self, call: ToolCall) -> ToolResult:
        """执行一次工具调用；可恢复错误转成结果，致命错误向上抛出。"""
        tool = self._registry.find(call.name)
        if tool is not None:
            return await self._execute_local(tool, call)

        resolved = await self._resolve_provider(call.name)
        if resolved is None:
            return _error(call, "unknown_tool", f"未注册的工具: {call.name}")
        provider, spec = resolved
        return await self._execute_provider(provider, spec, call)

    async def execute_many(self, calls: Sequence[ToolCall]) -> list[ToolResult]:
        """同一批调用并行执行，返回顺序与入参一致。"""
        if not calls:
            return []
        return list(await asyncio.gather(*(self.execute(call) for call in calls)))

    async def _execute_local(self, tool: Tool, call: ToolCall) -> ToolResult:
        validation_error = _validate(tool.name, tool.parameters, call.arguments)
        if validation_error is not None:
            return _error(call, "validation", validation_error)

        async def invoke() -> str:
            if self._sandbox is not None:
                return await self._sandbox.execute(tool, call.arguments)
            return await tool.run(**call.arguments)

        return await self._guarded(call, invoke)

    async def _execute_provider(
        self, provider: ToolProvider, spec: ToolSpec, call: ToolCall
    ) -> ToolResult:
        validation_error = _validate(spec.name, spec.parameters, call.arguments)
        if validation_error is not None:
            return _error(call, "validation", validation_error)

        async def invoke() -> str:
            return await provider.call(call.name, call.arguments)

        return await self._guarded(call, invoke)

    async def _guarded(self, call: ToolCall, invoke: Callable[[], Awaitable[str]]) -> ToolResult:
        try:
            output = await asyncio.wait_for(invoke(), timeout=self._timeout)
        except TimeoutError:
            return _error(call, "timeout", f"工具 {call.name} 执行超时（{self._timeout}s）")
        except ToolError as exc:
            if exc.recoverable:
                return _error(call, "execution", str(exc))
            raise
        except Exception as exc:  # noqa: BLE001 - 未预期异常默认回填给模型
            return _error(call, "execution", str(exc))
        return ToolResult(tool_call_id=call.id, name=call.name, content=output)

    async def _resolve_provider(self, name: str) -> tuple[ToolProvider, ToolSpec] | None:
        for provider in self._providers:
            for spec in await provider.list_tools():
                if spec.name == name:
                    return provider, spec
        return None


def _validate(tool_name: str, schema: dict[str, Any], arguments: dict[str, Any]) -> str | None:
    """按 JSON Schema 校验参数；返回错误描述，合法时返回 None。"""
    try:
        validator = Draft202012Validator(schema)
    except SchemaError as exc:
        raise ToolError(f"工具 {tool_name} 的 JSON Schema 非法: {exc}", recoverable=False) from exc

    errors = sorted(validator.iter_errors(arguments), key=lambda e: list(e.absolute_path))
    if not errors:
        return None
    messages = []
    for error in errors:
        path = "/".join(str(part) for part in error.absolute_path) or "<root>"
        messages.append(f"{path}: {error.message}")
    return "; ".join(messages)


def _error(
    call: ToolCall, error_type: str, message: str, *, recoverable: bool = True
) -> ToolResult:
    return ToolResult(
        tool_call_id=call.id,
        name=call.name,
        error=message,
        error_type=error_type,
        recoverable=recoverable,
    )
