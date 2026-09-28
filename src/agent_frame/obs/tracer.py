"""可观测性：结构化日志 + 调用追踪（简单实现）。

后续可扩展为 OpenTelemetry、调用链记录、token 用量统计等。
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any, Protocol

logger = logging.getLogger("agent_frame")

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")


class Tracer(Protocol):
    def log_llm_call(self, messages: Any, tools: Any | None = None) -> None: ...

    def log_tool_call(self, name: str, arguments: dict, output: str) -> None: ...


class ConsoleTracer:
    """把调用过程打到标准日志的简单 Tracer。"""

    def log_llm_call(self, messages: Any, tools: Any | None = None) -> None:
        logger.info(
            "[trace=%s] LLM 调用，消息数=%d，工具数=%d",
            _trace_id.get(),
            len(messages),
            len(tools or []),
        )

    def log_tool_call(self, name: str, arguments: dict, output: str) -> None:
        logger.info(
            "[trace=%s] 工具 %s(%r) → %s",
            _trace_id.get(),
            name,
            arguments,
            output[:200],
        )


def new_trace_id() -> str:
    """生成并设置一个当前上下文的 trace id。"""
    tid = uuid.uuid4().hex[:12]
    _trace_id.set(tid)
    return tid
