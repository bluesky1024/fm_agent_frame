"""网格标注：在截图上叠加网格线与行列标尺，供视觉模型读取行列号。"""

from __future__ import annotations

from typing import Protocol

from PIL import Image, ImageDraw

_LINE = (255, 0, 0)
_LABEL = (0, 0, 255)


class GridGeometry(Protocol):
    """标注所需的最小几何协议（1 基行列，图像坐标系）。"""

    origin_x: int
    origin_y: int
    cell_w: int
    cell_h: int
    rows: int
    cols: int


class Annotator(Protocol):
    def draw(self, image: Image.Image) -> Image.Image: ...


class GridAnnotator:
    """按几何在图像上画网格线和 1 基行列标尺。

    传入的几何应处于「图像坐标系」（即已按截屏区域偏移过）。
    """

    def __init__(self, geometry: GridGeometry) -> None:
        self.geometry = geometry

    def draw(self, img: Image.Image) -> Image.Image:
        out = img.convert("RGB").copy()
        draw = ImageDraw.Draw(out)
        g = self.geometry

        right = g.origin_x + g.cols * g.cell_w
        bottom = g.origin_y + g.rows * g.cell_h

        for c in range(g.cols + 1):
            x = g.origin_x + c * g.cell_w
            draw.line([(x, g.origin_y), (x, bottom)], fill=_LINE, width=2)
        for r in range(g.rows + 1):
            y = g.origin_y + r * g.cell_h
            draw.line([(g.origin_x, y), (right, y)], fill=_LINE, width=2)

        for r in range(1, g.rows + 1):
            y = g.origin_y + (r - 1) * g.cell_h + g.cell_h // 2
            draw.text((g.origin_x - 18, y - 6), str(r), fill=_LABEL)
        for c in range(1, g.cols + 1):
            x = g.origin_x + (c - 1) * g.cell_w + g.cell_w // 2
            draw.text((x - 4, g.origin_y - 16), str(c), fill=_LABEL)

        return out
