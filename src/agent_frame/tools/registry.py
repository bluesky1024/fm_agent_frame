"""工具注册表：注册、查找与导出 schema。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from agent_frame.core.errors import ToolError
from agent_frame.core.types import ToolSpec
from agent_frame.tools.base import Tool, to_tool_spec


class ToolRegistry:
    """按名字管理一组工具，并提供给 LLM 的 schema 与统一执行入口。"""

    def __init__(self, tools: Sequence[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ToolError(f"工具名重复: {tool.name}")
        self._tools[tool.name] = tool

    def find(self, name: str) -> Tool | None:
        """按名字查找工具，不存在返回 None。"""
        return self._tools.get(name)

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolError(f"未注册的工具: {name}") from exc

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def tools(self) -> list[Tool]:
        return list(self._tools.values())

    def to_tool_specs(self) -> list[ToolSpec]:
        """转成给 LLM 描述的工具列表。"""
        return [to_tool_spec(t) for t in self._tools.values()]

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        """按名字执行一个工具（不做校验，供旧 Agent 使用）。"""
        tool = self.get(name)
        return await tool.run(**arguments)
