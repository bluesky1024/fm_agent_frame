"""Session 具体实现：持有记忆、历史、状态与上次运行结果。

SessionManager（多会话管理）在票 09 补齐。
"""

from __future__ import annotations

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
