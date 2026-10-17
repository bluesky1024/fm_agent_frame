"""检索增强（RAG）协议：加载、切块、向量化、存取、检索与重排。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel, Field


class Document(BaseModel):
    """一段原始文档（知识库的输入单元）。"""

    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """文档切分后的一段块（索引与检索的基本单位）。"""

    chunk_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoredChunk(BaseModel):
    """检索命中的块，附带相关度分数。"""

    chunk: Chunk
    score: float


class Loader(Protocol):
    async def load(self, source: str) -> list[Document]: ...


class Chunker(Protocol):
    def chunk(self, document: Document) -> list[Chunk]: ...


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class VectorStore(Protocol):
    async def add(self, chunks: Sequence[Chunk], embeddings: Sequence[list[float]]) -> None: ...

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[ScoredChunk]: ...

    async def delete(self, chunk_ids: Sequence[str]) -> None: ...


class Reranker(Protocol):
    async def rerank(
        self, query: str, candidates: Sequence[ScoredChunk], *, top_k: int = 5
    ) -> list[ScoredChunk]: ...


class Retriever(Protocol):
    async def retrieve(
        self, query: str, *, top_k: int = 5, filter: dict[str, Any] | None = None
    ) -> list[ScoredChunk]: ...
