"""最小检索流水线：确定性 embedder + 内存向量库 + 上下文提供者。

确定性 embedder 不访问外部服务：按 token 哈希到固定维度向量，
同样的文本永远得到同样的向量，测试可复现。
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Any

from agent_frame.capabilities.retrieval.base import (
    Chunk,
    Chunker,
    Document,
    Embedder,
    ScoredChunk,
    VectorStore,
)
from agent_frame.context.providers import ContextRequest
from agent_frame.core.messages import Message

_TOKEN_RE = re.compile(r"[a-z0-9]+|[一-鿿]")


class DeterministicEmbedder:
    """把文本哈希成固定维度、归一化的向量。"""

    def __init__(self, dimensions: int = 64) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions 必须为正数")
        self.dimensions = dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class SimpleChunker:
    """按空行分段，并把过长的段落按最大长度切开。"""

    def __init__(self, max_chars: int = 200) -> None:
        self._max_chars = max_chars

    def chunk(self, document: Document) -> list[Chunk]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", document.content)]
        chunks: list[Chunk] = []
        for part in paragraphs:
            if not part:
                continue
            for start in range(0, len(part), self._max_chars):
                text = part[start : start + self._max_chars]
                digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
                chunks.append(
                    Chunk(
                        chunk_id=f"{digest}-{len(chunks)}",
                        content=text,
                        metadata=dict(document.metadata),
                    )
                )
        return chunks


class InMemoryVectorStore:
    """进程内向量库：余弦相似度暴力检索。"""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._embeddings: list[list[float]] = []

    async def add(self, chunks: Sequence[Chunk], embeddings: Sequence[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks 与 embeddings 数量不一致")
        self._chunks.extend(chunks)
        self._embeddings.extend(embeddings)

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[ScoredChunk]:
        scored: list[ScoredChunk] = []
        for chunk, embedding in zip(self._chunks, self._embeddings):
            if filter and any(chunk.metadata.get(k) != v for k, v in filter.items()):
                continue
            scored.append(ScoredChunk(chunk=chunk, score=_cosine(query_vector, embedding)))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    async def delete(self, chunk_ids: Sequence[str]) -> None:
        targets = set(chunk_ids)
        kept = [
            (chunk, embedding)
            for chunk, embedding in zip(self._chunks, self._embeddings)
            if chunk.chunk_id not in targets
        ]
        self._chunks = [chunk for chunk, _ in kept]
        self._embeddings = [embedding for _, embedding in kept]


class SimpleRetriever:
    """编排 Embedder + VectorStore 的最小在线检索。"""

    def __init__(
        self,
        embedder: Embedder | None = None,
        store: VectorStore | None = None,
        chunker: Chunker | None = None,
    ) -> None:
        self._embedder = embedder or DeterministicEmbedder()
        self._store = store or InMemoryVectorStore()
        self._chunker = chunker or SimpleChunker()

    async def add_documents(self, documents: Sequence[Document]) -> int:
        chunks: list[Chunk] = []
        for document in documents:
            chunks.extend(self._chunker.chunk(document))
        if not chunks:
            return 0
        embeddings = await self._embedder.embed([chunk.content for chunk in chunks])
        await self._store.add(chunks, embeddings)
        return len(chunks)

    async def retrieve(
        self, query: str, *, top_k: int = 5, filter: dict[str, Any] | None = None
    ) -> list[ScoredChunk]:
        vectors = await self._embedder.embed([query])
        return await self._store.search(vectors[0], top_k=top_k, filter=filter)


class RetrievalContextProvider:
    """把检索命中的片段作为一条 system 消息注入请求视图。"""

    def __init__(self, retriever: SimpleRetriever, *, top_k: int = 3) -> None:
        self._retriever = retriever
        self._top_k = top_k

    async def provide(self, request: ContextRequest) -> list[Message]:
        results = await self._retriever.retrieve(request.input, top_k=self._top_k)
        results = [item for item in results if item.score > 0]
        if not results:
            return []
        lines = "\n".join(f"- {item.chunk.content}" for item in results)
        return [Message.system(f"相关背景资料：\n{lines}")]


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
