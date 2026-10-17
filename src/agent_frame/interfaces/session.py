"""Session 与 SessionManager：多轮状态归属与多会话隔离。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from agent_frame.core.messages import Message
from agent_frame.core.types import AgentResult
from agent_frame.memory.base import Memory
from agent_frame.memory.conversation import ConversationMemory


@dataclass
class InMemorySession:
    """进程内会话：满足 runtime.Session 协议。"""

    id: str = "default"
    memory: Memory = field(default_factory=ConversationMemory)
    history: list[Message] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    last_run: AgentResult | None = None


class SessionManager:
    """按 session_id 管理多个会话；每个会话拥有独立记忆。"""

    def __init__(self) -> None:
        self._sessions: dict[str, InMemorySession] = {}

    def create(self, session_id: str | None = None) -> InMemorySession:
        sid = session_id or uuid.uuid4().hex[:12]
        if sid in self._sessions:
            raise ValueError(f"会话已存在: {sid}")
        session = InMemorySession(id=sid)
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> InMemorySession | None:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str | None) -> InMemorySession:
        if session_id is None:
            return self.create()
        existing = self.get(session_id)
        return existing if existing is not None else self.create(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def ids(self) -> list[str]:
        return list(self._sessions)
