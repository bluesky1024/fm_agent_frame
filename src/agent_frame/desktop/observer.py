"""BoardObserver：截屏 → 叠加网格 → 组装成带图 user 消息。"""

from __future__ import annotations

import io

from PIL import Image

from agent_frame.core.messages import Message
from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.screen import ScreenCapture

_DEFAULT_CAPTION = (
    "这是当前扫雷棋盘的截图，每个格子外侧已标注 1 基行列号。请根据棋盘状态决定下一步动作。"
)


class BoardObserver:
    """实现 Observer 协议：每轮提供一帧最新棋盘图。"""

    def __init__(
        self,
        capture: ScreenCapture,
        geometry: BoardGeometry,
        *,
        detail: str = "high",
        max_px: int = 1300,
        caption: str = _DEFAULT_CAPTION,
    ) -> None:
        self._capture = capture
        # 把屏幕绝对坐标平移到截屏图像坐标，供标注使用
        offset = geometry.translated(-capture.region.left, -capture.region.top)
        self.annotator = GridAnnotator(offset)
        self._detail = detail
        self._max_px = max_px
        self._caption = caption

    async def observe(self) -> Message:
        img = self._capture.grab()
        img = self.annotator.draw(img)
        img = _downscale(img, self._max_px)
        return Message.user_with_image(self._caption, _to_png(img), detail=self._detail)


def _downscale(img: Image.Image, max_px: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_px:
        return img
    scale = max_px / max(w, h)
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))))


def _to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
