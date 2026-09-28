"""工具抽象：Tool 协议 + 把 Tool 转成 LLM 可识别的 ToolSpec。"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol

from agent_frame.llm.base import ToolSpec


class Tool(Protocol):
    """一个可被 Agent 调用的工具。

    实现约定：
    - name / description / parameters 用类变量声明；
      parameters 是一段 JSON Schema，告诉 LLM 这个工具接受哪些参数。
    - run 接收 **kwargs（对应 JSON Schema 里的参数），返回一段文本结果。
    """

    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict[str, Any]]

    async def run(self, **kwargs: Any) -> str: ...


def to_tool_spec(tool: Tool) -> ToolSpec:
    """把一个 Tool 转成给 LLM 描述的 ToolSpec。"""
    return ToolSpec(
        name=tool.name, description=tool.description, parameters=tool.parameters
    )
