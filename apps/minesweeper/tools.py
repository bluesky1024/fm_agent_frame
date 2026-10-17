"""扫雷工具：click_cell / flag_cell。

鼠标等同步调用通过 ``asyncio.to_thread`` 隔离，避免阻塞事件循环。
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from agent_frame.capabilities.computer_use import MouseController
from agent_frame.core.errors import ToolError
from apps.minesweeper.board import BoardGeometry
from apps.minesweeper.board_state import BoardProbe


class ClickCellTool:
    name: ClassVar[str] = "click_cell"
    description: ClassVar[str] = (
        "翻开指定的格子（左键单击该格中心）。row/col 为 1 基行列号，与棋盘截图上标注的行列号一致。"
    )
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "row": {"type": "integer", "description": "行号（1 基，从上往下）"},
            "col": {"type": "integer", "description": "列号（1 基，从左往右）"},
        },
        "required": ["row", "col"],
    }

    def __init__(
        self,
        geometry: BoardGeometry,
        mouse: MouseController,
        *,
        probe: BoardProbe | None = None,
    ) -> None:
        self._geometry = geometry
        self._mouse = mouse
        self._probe = probe

    async def run(self, row: int, col: int) -> str:
        if self._probe is not None:
            state = self._probe.cell_state(row, col)
            if state == "revealed":
                raise ToolError(
                    f"格子 ({row}, {col}) 已经翻开，请选择其他未翻开的格子。",
                    recoverable=True,
                )
            if state == "flagged":
                raise ToolError(
                    f"格子 ({row}, {col}) 已插旗；如果确认它是雷就不要点开。",
                    recoverable=True,
                )
        x, y = self._geometry.cell_center(row, col)
        await asyncio.to_thread(self._mouse.click, x, y, button="left")
        return "ok"


class FlagCellTool:
    name: ClassVar[str] = "flag_cell"
    description: ClassVar[str] = (
        "给指定的格子插旗（标记为此处是雷）。row/col 为 1 基行列号，与棋盘截图上标注的行列号一致。"
    )
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "row": {"type": "integer", "description": "行号（1 基，从上往下）"},
            "col": {"type": "integer", "description": "列号（1 基，从左往右）"},
        },
        "required": ["row", "col"],
    }

    def __init__(self, geometry: BoardGeometry, mouse: MouseController) -> None:
        self._geometry = geometry
        self._mouse = mouse

    async def run(self, row: int, col: int) -> str:
        x, y = self._geometry.cell_center(row, col)
        await asyncio.to_thread(self._mouse.shift_click, x, y)
        return "ok"
