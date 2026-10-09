"""检索增强（RAG）抽象：从「文档摄取」到「在线检索」的完整能力面。

一条 RAG 流水线分两段：

- 离线侧（建索引）：Loader → Chunker → Embedder → VectorStore
- 在线侧（查询）：Retriever（编排 Embedder + VectorStore + 可选 Reranker）

本文件只定义接口（Protocol + 数据模型），不提供具体实现。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel, Field


# ---------- 数据模型 ----------


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


# ---------- 离线侧（建索引） ----------


class Loader(Protocol):
    """摄取：从来源加载原始文档。

    source 可以是文件路径、URL、数据库查询等。
    """

    async def load(self, source: str) -> list[Document]: ...


class Chunker(Protocol):
    """切分：把一篇文档切成若干块。

    块大小与重叠（overlap）会显著影响检索质量，属于 CPU 计算，故用同步。
    """

    def chunk(self, document: Document) -> list[Chunk]: ...


class Embedder(Protocol):
    """向量化：把文本批量转成向量（通常调用 embedding 服务，I/O 密集）。"""

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class VectorStore(Protocol):
    """向量存储：写入向量块，支持相似度检索与元数据过滤。"""

    async def add(
        self, chunks: Sequence[Chunk], embeddings: Sequence[list[float]]
    ) -> None: ...

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[ScoredChunk]: ...

    async def delete(self, chunk_ids: Sequence[str]) -> None: ...


# ---------- 在线侧（查询） ----------


class Reranker(Protocol):
    """重排序：对候选块按与 query 的相关性精排（通常用 cross-encoder）。"""

    async def rerank(
        self, query: str, candidates: Sequence[ScoredChunk], *, top_k: int = 5
    ) -> list[ScoredChunk]: ...


class Retriever(Protocol):
    """在线检索：把 query 变成相关块。

    一个典型的实现会编排 Embedder（query 向量化）+ VectorStore（相似度搜索）
    + 可选的 Reranker（精排）。
    """

    async def retrieve(
        self, query: str, *, top_k: int = 5, filter: dict[str, Any] | None = None
    ) -> list[ScoredChunk]: ...
