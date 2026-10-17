"""扫雷应用配置：把游戏自报的裸 dict 转成显式类型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Self

from agent_frame.capabilities.computer_use import CaptureRegion
from apps.minesweeper.board import BoardGeometry


@dataclass(frozen=True)
class RestartSpec:
    """重开方式：点击坐标或按键。"""

    kind: Literal["click", "key"]
    x: int = 0
    y: int = 0
    key: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        kind = data.get("type")
        if kind == "click":
            return cls(kind="click", x=int(data["x"]), y=int(data["y"]))
        if kind == "key":
            return cls(kind="key", key=str(data["key"]))
        raise ValueError(f"未知的 restart 类型: {kind}")


@dataclass(frozen=True)
class MinesweeperConfig:
    """扫雷 agent 的完整配置。"""

    geometry: BoardGeometry
    region: CaptureRegion
    restart: RestartSpec
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
            restart=RestartSpec.from_dict(config["restart"]),
            image_detail=config.get("image_detail", "high"),
            image_max_px=int(config.get("image_max_px", 1300)),
            max_steps=max_steps,
            tool_timeout=tool_timeout,
        )
