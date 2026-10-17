"""工具：翻开指定格子（左键单击）。"""

from __future__ import annotations

from typing import Any, ClassVar

from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController


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
        self._mouse.click(x, y, button="left")
        return "ok"
