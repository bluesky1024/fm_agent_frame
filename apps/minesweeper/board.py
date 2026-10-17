"""棋盘几何：行列号 ↔ 屏幕像素坐标换算。"""

from __future__ import annotations

from pydantic import BaseModel


class BoardGeometry(BaseModel):
    """棋盘在屏幕上的几何布局。

    origin_x/origin_y 是左上角格子外沿的屏幕绝对像素；
    cell_w/cell_h 是单格宽高；行列号约定为 1 基。
    """

    origin_x: int
    origin_y: int
    cell_w: int
    cell_h: int
    rows: int
    cols: int

    def cell_center(self, row: int, col: int) -> tuple[int, int]:
        """把 1 基行列号换算成屏幕像素的格子中心坐标。"""
        if not (1 <= row <= self.rows):
            raise ValueError(f"行号越界: {row}，合法范围 1..{self.rows}")
        if not (1 <= col <= self.cols):
            raise ValueError(f"列号越界: {col}，合法范围 1..{self.cols}")
        x = self.origin_x + (col - 1) * self.cell_w + self.cell_w // 2
        y = self.origin_y + (row - 1) * self.cell_h + self.cell_h // 2
        return x, y

    def translated(self, dx: int, dy: int) -> "BoardGeometry":
        """返回平移后的副本（只改原点）。用于屏幕坐标 → 截屏图像坐标。"""
        return self.model_copy(
            update={"origin_x": self.origin_x + dx, "origin_y": self.origin_y + dy}
        )
