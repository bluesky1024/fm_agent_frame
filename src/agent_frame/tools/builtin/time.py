"""内置工具：取当前日期时间。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar


class CurrentTimeTool:
    name: ClassVar[str] = "get_current_time"
    description: ClassVar[str] = "获取当前的日期和时间。"
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    async def run(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
