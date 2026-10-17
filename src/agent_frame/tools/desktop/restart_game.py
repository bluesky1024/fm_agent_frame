"""工具：重开一局（点击重开按钮或发按键）。"""

from __future__ import annotations

from typing import Any, ClassVar

from agent_frame.desktop.mouse import MouseController
from agent_frame.errors import ToolError


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
            self._mouse.click(x, y, button="left")
            return "ok"
        self._mouse.press(self._key)  # type: ignore[arg-type]
        return "ok"
