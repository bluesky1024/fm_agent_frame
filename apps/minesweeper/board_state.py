"""从截图像素识别扫雷棋盘状态。

依赖目标游戏的固定配色（见 ``games/minesweeper.py``）：
未翻开 ``#bbbbbb``、已翻开 ``#e0e0e0``、插旗 ``#cccccc``、踩雷红字 ``*``。
采样格子内部的多数颜色，避开红色网格标注线与数字/旗子字形。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image

from apps.minesweeper.board import BoardGeometry

COVERED = (187, 187, 187)
REVEALED = (224, 224, 224)
FLAGGED = (204, 204, 204)

_KNOWN = {COVERED: "covered", REVEALED: "revealed", FLAGGED: "flagged"}


@dataclass(frozen=True)
class BoardState:
    """一张截图里读取到的棋盘计数。"""

    rows: int
    cols: int
    revealed: int = 0
    covered: int = 0
    flagged: int = 0
    unknown: int = 0
    exploded: bool = False

    @property
    def total(self) -> int:
        return self.rows * self.cols

    @property
    def unrevealed(self) -> int:
        return self.covered + self.flagged

    def is_won(self, mines: int) -> bool:
        return (
            self.unknown == 0
            and not self.exploded
            and self.revealed == self.total - mines
        )

    def is_lost(self) -> bool:
        return self.exploded

    def describe(self) -> str:
        text = (
            f"已翻开 {self.revealed} 格，未翻开 {self.unrevealed} 格"
            f"（其中插旗 {self.flagged} 面）"
        )
        if self.unknown:
            text += f"，无法识别 {self.unknown} 格"
        return text


def analyze_board(image: Image.Image, geometry: BoardGeometry) -> BoardState:
    """以图像坐标系的几何扫描整盘，返回棋盘计数。"""
    counts = Counter()
    exploded = False
    for row in range(1, geometry.rows + 1):
        for col in range(1, geometry.cols + 1):
            state = classify_cell(image, geometry, row, col)
            counts[state] += 1
            if state == "revealed" and _has_red_marker(image, geometry, row, col):
                exploded = True
    return BoardState(
        rows=geometry.rows,
        cols=geometry.cols,
        revealed=counts["revealed"],
        covered=counts["covered"],
        flagged=counts["flagged"],
        unknown=counts["unknown"],
        exploded=exploded,
    )


class BoardProbe:
    """用最近一帧截图回答「这一格现在是什么状态」。"""

    def __init__(
        self,
        image: Callable[[], Image.Image | None],
        geometry: BoardGeometry,
    ) -> None:
        self._image = image
        self._geometry = geometry

    def cell_state(self, row: int, col: int) -> str:
        image = self._image()
        if image is None:
            return "unknown"
        return classify_cell(image, self._geometry, row, col)


def classify_cell(image: Image.Image, geometry: BoardGeometry, row: int, col: int) -> str:
    """返回 ``revealed`` / ``covered`` / ``flagged`` / ``unknown``。"""
    background = _background(image, geometry, row, col)
    return _KNOWN.get(background, "unknown") if background is not None else "unknown"


def cell_origin(geometry: BoardGeometry, row: int, col: int) -> tuple[int, int]:
    return (
        geometry.origin_x + (col - 1) * geometry.cell_w,
        geometry.origin_y + (row - 1) * geometry.cell_h,
    )


def _background(
    image: Image.Image, geometry: BoardGeometry, row: int, col: int
) -> tuple[int, int, int] | None:
    x0, y0 = cell_origin(geometry, row, col)
    counts: Counter[tuple[int, int, int]] = Counter()
    for fx in (0.25, 0.5, 0.75):
        for fy in (0.25, 0.5, 0.75):
            x = x0 + max(1, int(geometry.cell_w * fx))
            y = y0 + max(1, int(geometry.cell_h * fy))
            pixel = image.getpixel((x, y))
            if pixel in _KNOWN:
                counts[pixel] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _has_red_marker(
    image: Image.Image, geometry: BoardGeometry, row: int, col: int
) -> bool:
    """已翻开格里的红色像素只可能来自踩雷的 ``*``。"""
    x0, y0 = cell_origin(geometry, row, col)
    margin_x = max(2, geometry.cell_w // 4)
    margin_y = max(2, geometry.cell_h // 4)
    red_pixels = 0
    for x in range(x0 + margin_x, x0 + geometry.cell_w - margin_x):
        for y in range(y0 + margin_y, y0 + geometry.cell_h - margin_y):
            r, g, b = image.getpixel((x, y))
            if r > 150 and g < 90 and b < 90:
                red_pixels += 1
                if red_pixels >= 3:  # 抗锯齿可能产生单个红色像素
                    return True
    return False
