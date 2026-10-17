"""工具执行沙箱：首版提供 no-op 实现，真实接入 ToolExecutor。"""

from __future__ import annotations

from typing import Any

from agent_frame.tools.base import Tool, ToolSandbox

__all__ = ["NoopToolSandbox", "ToolSandbox"]


class NoopToolSandbox:
    """不做隔离，直接在当前进程执行工具。"""

    async def execute(self, tool: Tool, arguments: dict[str, Any]) -> str:
        return await tool.run(**arguments)
