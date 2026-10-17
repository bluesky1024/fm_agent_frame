"""Human-in-the-loop：自动批准与控制台审批，审批记录可查询。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from agent_frame.core.messages import ToolCall
from agent_frame.runtime.policies import ApprovalDecision, RunContext


@dataclass
class ApprovalRecord:
    """一次审批决定（可按 call_id 查询）。"""

    call_id: str
    tool_name: str
    approved: bool
    reason: str | None = None
    decided_at: datetime = field(default_factory=datetime.now)


class AutoApprove:
    """自动批准：默认策略，行为与未接线时一致。"""

    def __init__(self) -> None:
        self.records: list[ApprovalRecord] = []

    async def approve(self, call: ToolCall, *, context: RunContext) -> ApprovalDecision:
        self.records.append(
            ApprovalRecord(
                call_id=call.id,
                tool_name=call.name,
                approved=True,
                reason="auto",
            )
        )
        return ApprovalDecision(approved=True, reason="auto")

    def status(self, call_id: str) -> ApprovalRecord | None:
        for record in reversed(self.records):
            if record.call_id == call_id:
                return record
        return None


class ConsoleApprove:
    """控制台审批：默认向终端询问 y/N；测试可注入 ask 函数。"""

    def __init__(self, ask: Callable[[ToolCall], bool] | None = None) -> None:
        self._ask = ask or _ask_console
        self.records: list[ApprovalRecord] = []

    async def approve(self, call: ToolCall, *, context: RunContext) -> ApprovalDecision:
        approved = await asyncio.to_thread(self._ask, call)
        reason = "控制台批准" if approved else "控制台拒绝"
        self.records.append(
            ApprovalRecord(
                call_id=call.id,
                tool_name=call.name,
                approved=approved,
                reason=reason,
            )
        )
        return ApprovalDecision(approved=approved, reason=reason)

    def status(self, call_id: str) -> ApprovalRecord | None:
        for record in reversed(self.records):
            if record.call_id == call_id:
                return record
        return None


def _ask_console(call: ToolCall) -> bool:
    answer = input(f"批准工具调用 {call.name}({call.arguments})？[y/N] ")
    return answer.strip().lower() in ("y", "yes")
