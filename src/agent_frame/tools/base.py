"""工具抽象：自包含的 Tool / ToolResult / ToolProvider / ToolSandbox 协议。

本层只依赖 ``core``：工具定义、执行结果与动态提供者都不引用 LLM 类型。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, ClassVar, Protocol

from pydantic import BaseModel

from agent_frame.core.types import ToolSpec

__all__ = ["Tool", "ToolProvider", "ToolResult", "ToolSandbox", "ToolSpec", "to_tool_spec"]


class Tool(Protocol):
    """一个可被 Agent 调用的工具。

    实现约定：
    - name / description / parameters 用类变量声明；
      parameters 是一段 JSON Schema，告诉 LLM 这个工具接受哪些参数。
    - run 接收 JSON Schema 里声明的参数（各工具签名不同），返回一段文本结果。
    """

    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict[str, Any]]

    # run 的具体参数由 parameters(JSON Schema) 动态决定，静态类型无法逐一定义；
    # 用 Callable[..., Awaitable[str]] 表示「任意参数、返回可等待的字符串」。
    run: Callable[..., Awaitable[str]]


class ToolResult(BaseModel):
    """一次工具执行的结构化结果。

    - 成功：``content`` 有值；
    - 失败：``error`` / ``error_type`` 有值，``recoverable`` 表示是否可回填给模型。
    """

    tool_call_id: str
    name: str
    content: str | None = None
    error: str | None = None
    error_type: str | None = None
    recoverable: bool = True

    @property
    def ok(self) -> bool:
        return self.error is None


class ToolProvider(Protocol):
    """动态工具提供者（如 MCP）：在运行时提供额外工具并执行。"""

    async def list_tools(self) -> Sequence[ToolSpec]: ...

    async def call(self, name: str, arguments: dict[str, Any]) -> str: ...


class ToolSandbox(Protocol):
    """工具执行沙箱：包装本地工具调用，首版可以是 no-op。"""

    async def execute(self, tool: Tool, arguments: dict[str, Any]) -> str: ...


def to_tool_spec(tool: Tool) -> ToolSpec:
    """把一个 Tool 转成给 LLM 描述的 ToolSpec。"""
    return ToolSpec(name=tool.name, description=tool.description, parameters=tool.parameters)
