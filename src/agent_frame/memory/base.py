"""记忆抽象：定义 Agent 所需的多层记忆能力。

LLM 是无状态的，记忆系统负责在多次调用之间保存与召回上下文。
业界通常把记忆分成多层、各司其职：

- 短期对话记忆（Memory）：按会话回放完整的消息历史
- 用户画像（ProfileMemory）：跨会话持久的用户稳定事实
- 语义记忆（SemanticMemory）：从对话中提炼出的长期事实，按相关性召回
- 情景记忆（EpisodicMemory）：带时间戳的具体事件
- 摘要压缩（Summarizer / SummaryBufferMemory）：超过阈值把旧历史压成摘要，省 token

本文件只定义接口（Protocol + 数据模型），不提供具体实现。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel, Field

from agent_frame.core.messages import Message

# ---------- 短期对话记忆 ----------


class Memory(Protocol):
    """短期对话记忆：按 session 存取完整消息历史。

    这是最基础的一层，等价于「会话缓冲」——把每次对话的消息原样存起来，
    下一次 run() 前取回来拼进 messages，实现跨轮次的连贯对话。
    """

    async def load(self, session_id: str) -> list[Message]:
        """取回某个会话的完整消息历史。"""
        ...

    async def save(self, session_id: str, messages: Sequence[Message]) -> None:
        """保存某个会话的消息历史（通常整段覆盖）。"""
        ...


# ---------- 用户画像 ----------


class UserProfile(BaseModel):
    """用户画像：跨会话持久的结构化信息。

    区别于「说了什么」（对话历史），画像是「这个用户是谁」的稳定事实，
    例如身份、语言、时区、偏好、约束等。
    """

    user_id: str
    name: str | None = None
    language: str | None = None
    timezone: str | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)


class ProfileMemory(Protocol):
    """用户画像记忆：保存并查询用户的长期稳定事实。"""

    async def get(self, user_id: str) -> UserProfile | None:
        """按 user_id 取画像，不存在返回 None。"""
        ...

    async def upsert(self, profile: UserProfile) -> None:
        """写入或更新画像。"""
        ...

    async def delete(self, user_id: str) -> None:
        """删除画像。"""
        ...


# ---------- 语义记忆 ----------


class Fact(BaseModel):
    """一条被提炼出的长期事实。

    和「原话」不同，事实是从对话里抽象出来的结构化结论，
    例如「用户的项目后端使用 Redis」。importance 用于记忆淘汰。
    """

    fact_id: str
    content: str
    source: str | None = None
    importance: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticMemory(Protocol):
    """长期语义记忆：记住事实，按相关性召回。"""

    async def remember(self, fact: Fact) -> None:
        """记住一条事实。"""
        ...

    async def recall(self, query: str, *, top_k: int = 5) -> list[Fact]:
        """按与 query 的相关性召回 top_k 条事实。"""
        ...

    async def forget(self, fact_id: str) -> None:
        """删除一条事实。"""
        ...


# ---------- 情景记忆 ----------


class Episode(BaseModel):
    """一条情景记忆：某次发生的具体事件。"""

    episode_id: str
    content: str
    occurred_at: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class EpisodicMemory(Protocol):
    """情景记忆：记录具体事件，支持按时间或相关性回溯。"""

    async def record(self, episode: Episode) -> None:
        """记录一个事件。"""
        ...

    async def query(self, *, since: float | None = None, top_k: int = 10) -> list[Episode]:
        """回溯事件：可按 since（Unix 时间戳）过滤，返回 top_k 条。"""
        ...


# ---------- 组合 ----------


class AgentMemory(Protocol):
    """Agent 可用的完整记忆集合，把各层记忆组合在一起。

    一个「完整」的 Agent 不再只依赖短期对话记忆，而是同时拥有：
    对话缓冲 + 用户画像 + 语义事实 + 情景事件。
    """

    conversation: Memory
    profile: ProfileMemory
    semantic: SemanticMemory
    episodic: EpisodicMemory


# ---------- 摘要压缩（预留，未实现） ----------


class MemorySummary(BaseModel):
    """一段对话历史的摘要（用于省 token 的上下文压缩）。"""

    content: str
    message_count: int = 0
    token_count: int = 0
    created_at: float = 0.0


class Summarizer(Protocol):
    """摘要器：把一段消息历史压缩成摘要（通常 LLM 驱动）。"""

    async def summarize(self, messages: Sequence[Message]) -> str: ...


class SummaryBufferMemory(Protocol):
    """「摘要 + 缓冲」记忆：更早历史压成摘要，最近几轮保留原文。

    - load 返回「摘要 + 最近原文」拼成的消息列表（摘要放最前，缓存友好）
    - compact 把最旧的消息折叠进摘要；触发时机由实现决定（如 token 阈值）
    """

    async def load(self, session_id: str) -> list[Message]: ...

    async def save(self, session_id: str, messages: Sequence[Message]) -> None: ...

    async def compact(self, session_id: str) -> None: ...
