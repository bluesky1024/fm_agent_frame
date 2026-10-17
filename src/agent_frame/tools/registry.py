"""工具注册表：注册、查找、转 OpenAI 格式、执行。"""

from __future__ import annotations

from collections.abc import Sequence

from agent_frame.core.errors import ToolError
from agent_frame.llm.base import ToolSpec
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

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolError(f"未注册的工具: {name}") from exc

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def to_tool_specs(self) -> list[ToolSpec]:
        """转成给 LLM 描述的工具列表。"""
        return [to_tool_spec(t) for t in self._tools.values()]

    async def call(self, name: str, arguments: dict) -> str:
        """按名字执行一个工具，返回文本结果。"""
        tool = self.get(name)
        return await tool.run(**arguments)
