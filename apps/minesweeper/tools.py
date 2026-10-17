"""扫雷工具：click_cell / flag_cell / restart_game。

鼠标等同步调用通过 ``asyncio.to_thread`` 隔离，避免阻塞事件循环。
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from agent_frame.capabilities.computer_use import MouseController
from agent_frame.core.errors import ToolError
from apps.minesweeper.board import BoardGeometry


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

    def __init__(self, geometry: BoardGeometry, mouse: MouseController) -> None:
        self._geometry = geometry
        self._mouse = mouse

    async def run(self, row: int, col: int) -> str:
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


class RestartGameTool:
    name: ClassVar[str] = "restart_game"
    description: ClassVar[str] = (
        "当本局已经结束（胜利，或踩到雷）时调用，重开一局新游戏。棋盘未结束时不要调用。"
    )
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    def __init__(
        self,
        mouse: MouseController,
        *,
        click_xy: tuple[int, int] | None = None,
        key: str | None = None,
    ) -> None:
        if (click_xy is None) == (key is None):
            raise ToolError("restart_game 需要且仅需一种重开方式：click_xy 或 key")
        self._mouse = mouse
        self._click_xy = click_xy
        self._key = key

    async def run(self) -> str:
        if self._click_xy is not None:
            x, y = self._click_xy
            await asyncio.to_thread(self._mouse.click, x, y, button="left")
            return "ok"
        if self._key is None:
            raise ToolError("restart_game 缺少重开方式", recoverable=False)
        await asyncio.to_thread(self._mouse.press, self._key)
        return "ok"
