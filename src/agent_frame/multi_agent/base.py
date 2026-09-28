"""多 Agent 编排抽象（打桩）。

后续学习「多个 Agent 如何协作」：任务拆分、分发、汇总等。
"""

from __future__ import annotations

from typing import Protocol


class AgentOrchestrator(Protocol):
    """多个 Agent 的协调者：拆分任务 → 分发 → 汇总结果。"""

    async def run(self, task: str) -> str: ...
