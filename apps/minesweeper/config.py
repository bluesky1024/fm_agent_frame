"""扫雷应用配置：把游戏自报的裸 dict 转成显式类型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from agent_frame.capabilities.computer_use import CaptureRegion
from apps.minesweeper.board import BoardGeometry


@dataclass(frozen=True)
class MinesweeperConfig:
    """扫雷 agent 的完整配置。"""

    geometry: BoardGeometry
    region: CaptureRegion
    mines: int
    image_detail: str = "high"
    image_max_px: int = 1300
    max_steps: int = 300
    tool_timeout: float = 30.0

    @classmethod
    def from_board_config(
        cls,
        config: dict[str, Any],
        *,
        max_steps: int = 300,
        tool_timeout: float = 30.0,
    ) -> Self:
        return cls(
            geometry=BoardGeometry(**config["geometry"]),
            region=CaptureRegion(**config["region"]),
            mines=int(config["mines"]),
            image_detail=config.get("image_detail", "high"),
            image_max_px=int(config.get("image_max_px", 1300)),
            max_steps=max_steps,
            tool_timeout=tool_timeout,
        )
