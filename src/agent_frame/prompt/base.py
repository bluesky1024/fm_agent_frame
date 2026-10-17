"""提示词抽象：从「模板渲染」到「版本管理 / 示例选择」的完整能力面。

业界把 prompt 当一等公民管理，能力包含：
- 模板渲染：变量替换、多消息角色（system/user/assistant 分段）
- 版本管理：命名 + 版本、可 pin、可回滚
- 少样本示例：按相关性动态挑选相关示例

本文件定义接口（Protocol + 数据模型）；StringTemplatePrompt 是最简参考实现。
"""

from __future__ import annotations

from string import Template
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from agent_frame.messages import Message

# ---------- 模板渲染 ----------


class PromptTemplate(Protocol):
    """模板：把模板 + 变量渲染成一段文本。"""

    def render(self, **variables: Any) -> str: ...

    def partial(self, **variables: Any) -> "PromptTemplate":
        """预填部分变量，返回一个新的模板（便于复用公共片段）。"""
        ...


class MessageTemplate(BaseModel):
    """一条多消息模板（system / user / assistant 各一段）。"""

    role: Literal["system", "user", "assistant"]
    template: str


class ChatPromptTemplate(Protocol):
    """多消息模板：把多段角色模板渲染成消息列表。"""

    def render_messages(self, **variables: Any) -> list[Message]: ...


# ---------- 版本管理 ----------


class Prompt(BaseModel):
    """一个带版本的 prompt。"""

    name: str
    version: str
    template: str
    variables: list[str] = Field(default_factory=list)
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptLibrary(Protocol):
    """prompt 版本库：命名 + 版本的存取、列表、删除。"""

    async def get(self, name: str, version: str | None = None) -> Prompt:
        """按 name 取 prompt；version 为 None 时取最新版本。"""
        ...

    async def save(self, prompt: Prompt) -> None:
        """保存（发布）一个新版本。"""
        ...

    async def list_versions(self, name: str) -> list[str]:
        """列出某个 prompt 的所有版本号。"""
        ...

    async def delete(self, name: str, version: str) -> None:
        """删除某个版本。"""
        ...


# ---------- 少样本示例 ----------


class Example(BaseModel):
    """一条少样本示例。"""

    input: str
    output: str


class ExampleSelector(Protocol):
    """示例选择：按与输入的相关性挑选少样本示例。"""

    def select(self, input: str, *, k: int = 3) -> list[Example]: ...


# ---------- 最简参考实现 ----------


class StringTemplatePrompt:
    """用 string.Template 的极简实现，作为 PromptTemplate 的参考。"""

    def __init__(self, template: str, **partials: Any) -> None:
        self._template = Template(template)
        self._partials = partials

    def render(self, **variables: Any) -> str:
        return self._template.safe_substitute(**self._partials, **variables)

    def partial(self, **variables: Any) -> "StringTemplatePrompt":
        return StringTemplatePrompt(self._template.template, **{**self._partials, **variables})
