"""提示词模板抽象（打桩）。

目前只提供协议和一个基于 string.Template 的极简参考实现，
后续可扩展为支持多轮角色模板、变量校验等。
"""

from __future__ import annotations

from string import Template
from typing import Any, Protocol


class PromptTemplate(Protocol):
    def render(self, **variables: Any) -> str: ...


class StringTemplatePrompt:
    """用 string.Template 的极简实现，作为 PromptTemplate 的参考。"""

    def __init__(self, template: str) -> None:
        self._template = Template(template)

    def render(self, **variables: Any) -> str:
        return self._template.safe_substitute(**variables)
