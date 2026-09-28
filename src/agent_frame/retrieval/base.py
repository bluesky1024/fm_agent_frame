"""检索增强（RAG）抽象（打桩）。

后续可接入向量数据库 / 全文检索，为 Agent 提供「外部知识」。
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class Document(BaseModel):
    """一段被检索到的文本片段。"""

    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Retriever(Protocol):
    async def retrieve(self, query: str, *, top_k: int = 5) -> list[Document]: ...
