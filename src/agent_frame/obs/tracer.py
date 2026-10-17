"""事件驱动的追踪器：Console / JSONL 两种输出。

Tracer 是运行事件的消费者，不侵入 AgentRuntime 的循环逻辑。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from agent_frame.core.events import (
    AgentEvent,
    ContextBuilt,
    Error,
    LLMCompleted,
    LLMDelta,
    RunEnd,
    RunStart,
    StepStart,
    ToolCallRequested,
    ToolResult,
)


class Tracer(Protocol):
    """消费运行时事件。"""

    def on_event(self, event: AgentEvent) -> None: ...

    def close(self) -> None: ...


class ConsoleTracer:
    """把事件打到标准输出：适合教学示例与本地调试。"""

    def on_event(self, event: AgentEvent) -> None:
        if isinstance(event, RunStart):
            print(f"\n[trace] 运行开始 {event.run_id} session={event.session_id}")
        elif isinstance(event, StepStart):
            print(f"[trace] 步骤 {event.step}")
        elif isinstance(event, ContextBuilt):
            print(f"[trace] 上下文 {event.message_count} 条 / ~{event.token_estimate} tokens")
        elif isinstance(event, LLMDelta):
            print(event.text, end="", flush=True)
        elif isinstance(event, LLMCompleted):
            print(f"  [usage] {event.usage.model_dump()}")
        elif isinstance(event, ToolCallRequested):
            print(f"[trace] 工具请求 {event.tool_call.name} {event.tool_call.arguments}")
        elif isinstance(event, ToolResult):
            status = "失败" if event.error else "成功"
            print(f"[trace] 工具{status} {event.name}: {event.error or event.content}")
        elif isinstance(event, Error):
            print(f"[trace] 错误：{event.error}（recoverable={event.recoverable}）")
        elif isinstance(event, RunEnd):
            print(
                f"[trace] 运行结束 steps={event.result.steps} "
                f"tokens={event.result.usage.total_tokens}"
            )

    def close(self) -> None:
        return None


class JSONLTracer:
    """把每个事件写一行 JSON，供离线分析与评测复盘。"""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._path.open("w", encoding="utf-8")

    @property
    def path(self) -> Path:
        return self._path

    def on_event(self, event: AgentEvent) -> None:
        payload = event.model_dump(mode="json")
        self._file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()
