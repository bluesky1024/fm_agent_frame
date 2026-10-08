"""工具抽象：Tool 协议 + 把 Tool 转成 LLM 可识别的 ToolSpec。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, ClassVar, Protocol

from agent_frame.llm.base import ToolSpec


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


def to_tool_spec(tool: Tool) -> ToolSpec:
    """把一个 Tool 转成给 LLM 描述的 ToolSpec。"""
    return ToolSpec(
        name=tool.name, description=tool.description, parameters=tool.parameters
    )
