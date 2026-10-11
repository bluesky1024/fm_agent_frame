"""网格标注：在棋盘截图上叠加网格线与行列标尺，供视觉模型读取行列号。"""

from __future__ import annotations

from PIL import Image, ImageDraw

from agent_frame.desktop.geometry import BoardGeometry

_LINE = (255, 0, 0)
_LABEL = (0, 0, 255)


class GridAnnotator:
    """按几何在图像上画网格线和 1 基行列标尺。

    传入的几何应处于「图像坐标系」（即已按截屏区域偏移过）。
    """

    def __init__(self, geometry: BoardGeometry) -> None:
        self.geometry = geometry

    def draw(self, img: Image.Image) -> Image.Image:
        out = img.convert("RGB").copy()
        draw = ImageDraw.Draw(out)
        g = self.geometry

        right = g.origin_x + g.cols * g.cell_w
        bottom = g.origin_y + g.rows * g.cell_h

        # 竖线（列边界）
        for c in range(g.cols + 1):
            x = g.origin_x + c * g.cell_w
            draw.line([(x, g.origin_y), (x, bottom)], fill=_LINE, width=2)
        # 横线（行边界）
        for r in range(g.rows + 1):
            y = g.origin_y + r * g.cell_h
            draw.line([(g.origin_x, y), (right, y)], fill=_LINE, width=2)

        # 行号（左侧，1 基）
        for r in range(1, g.rows + 1):
            y = g.origin_y + (r - 1) * g.cell_h + g.cell_h // 2
            draw.text((g.origin_x - 18, y - 6), str(r), fill=_LABEL)
        # 列号（顶部，1 基）
        for c in range(1, g.cols + 1):
            x = g.origin_x + (c - 1) * g.cell_w + g.cell_w // 2
            draw.text((x - 4, g.origin_y - 16), str(c), fill=_LABEL)

        return out
