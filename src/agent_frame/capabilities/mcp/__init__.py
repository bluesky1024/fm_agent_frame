"""MCP 工具接入：客户端协议 + ToolProvider 适配器 + 空客户端。

没有真实 MCP 传输时，用 NullMCPClient 占位；适配器本身已真实接入
ToolExecutor 的 provider 链路。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from agent_frame.core.errors import ToolError
from agent_frame.core.types import ToolSpec


class MCPClient(Protocol):
    """任意 MCP 客户端的抽象（stdio / HTTP 等由具体实现决定）。"""

    async def list_tools(self) -> Sequence[ToolSpec]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str: ...


class MCPToolProvider:
    """把 MCP 客户端适配成运行时认识的 ToolProvider。"""

    def __init__(self, client: MCPClient) -> None:
        self._client = client

    async def list_tools(self) -> Sequence[ToolSpec]:
        return await self._client.list_tools()

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        return await self._client.call_tool(name, arguments)


class NullMCPClient:
    """空实现：不提供工具，直接调用时报可恢复错误。"""

    async def list_tools(self) -> Sequence[ToolSpec]:
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        raise ToolError(f"未接入 MCP 客户端，无法调用 {name}", recoverable=True)


__all__ = ["MCPClient", "MCPToolProvider", "NullMCPClient"]
