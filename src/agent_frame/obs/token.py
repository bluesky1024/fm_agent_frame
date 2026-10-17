"""Token 与耗时统计：按运行和步骤消费事件累加。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from agent_frame.core.events import (
    AgentEvent,
    LLMCompleted,
    RunEnd,
    RunStart,
    StepStart,
    ToolCallRequested,
)
from agent_frame.core.types import TokenUsage


@dataclass
class StepStats:
    step: int
    usage: TokenUsage = field(default_factory=TokenUsage)
    duration_ms: float = 0.0


@dataclass
class RunStats:
    run_id: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    steps: list[StepStats] = field(default_factory=list)
    tool_calls: int = 0
    duration_ms: float = 0.0


class TokenTracker:
    """作为 Tracer 使用：累计每次运行、每一步的 token 与耗时。"""

    def __init__(self) -> None:
        self.runs: list[RunStats] = []
        self._run: RunStats | None = None
        self._run_started_at = 0.0
        self._step_started_at = 0.0

    @property
    def latest(self) -> RunStats | None:
        return self.runs[-1] if self.runs else None

    def on_event(self, event: AgentEvent) -> None:
        now = time.perf_counter()
        if isinstance(event, RunStart):
            self._run = RunStats(run_id=event.run_id)
            self._run_started_at = now
            self._step_started_at = now
        elif isinstance(event, StepStart):
            self._finish_step(now)
            if self._run is not None:
                self._run.steps.append(StepStats(step=event.step))
                self._step_started_at = now
        elif isinstance(event, LLMCompleted):
            if self._run is None:
                return
            self._run.usage = self._run.usage + event.usage
            if self._run.steps:
                current = self._run.steps[-1]
                current.usage = current.usage + event.usage
        elif isinstance(event, ToolCallRequested):
            if self._run is not None:
                self._run.tool_calls += 1
        elif isinstance(event, RunEnd):
            self._finish_step(now)
            if self._run is not None:
                self._run.duration_ms = (now - self._run_started_at) * 1000
                self.runs.append(self._run)
                self._run = None

    def _finish_step(self, now: float) -> None:
        if self._run is not None and self._run.steps:
            current = self._run.steps[-1]
            if current.duration_ms == 0.0:
                current.duration_ms = (now - self._step_started_at) * 1000
