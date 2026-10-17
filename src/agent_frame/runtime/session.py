"""Session 协议：运行期间全部可变状态的归属。

AgentSpec 无状态、可复用；每个 Session 持有自己的历史、状态与上次运行结果。
具体实现位于 ``interfaces/session.py``，运行时只依赖本协议。
"""

from __future__ import annotations

from typing import Any, Protocol

from agent_frame.core.messages import Message
from agent_frame.core.types import AgentResult
from agent_frame.memory.base import Memory


class Session(Protocol):
    """运行状态载体。"""

    id: str
    memory: Memory
    history: list[Message]
    state: dict[str, Any]
    last_run: AgentResult | None
