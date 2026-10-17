"""通用屏幕观察：截屏 → 可选标注 → 组装成带图 user 消息。

同步的截屏/标注/编码通过 ``asyncio.to_thread`` 隔离，不阻塞事件循环。
"""

from __future__ import annotations

import asyncio
import io

from PIL import Image

from agent_frame.capabilities.computer_use.annotate import Annotator
from agent_frame.capabilities.computer_use.screen import ScreenCapture
from agent_frame.core.messages import Message

_DEFAULT_CAPTION = "这是当前屏幕的截图，请根据画面决定下一步动作。"


class ScreenObserver:
    """每次 observe() 提供一帧最新屏幕图像。"""

    def __init__(
        self,
        capture: ScreenCapture,
        *,
        annotator: Annotator | None = None,
        caption: str = _DEFAULT_CAPTION,
        detail: str = "high",
        max_px: int = 1300,
    ) -> None:
        self._capture = capture
        self.annotator = annotator
        self._caption = caption
        self._detail = detail
        self._max_px = max_px
        # 最近一帧原始截图（未标注、未缩放），供工具在动作前核对画面状态。
        self.last_image: Image.Image | None = None

    async def observe(self) -> Message:
        image = await asyncio.to_thread(self._capture.grab)
        self.last_image = image
        caption = self._caption_for(image)
        if self.annotator is not None:
            image = await asyncio.to_thread(self.annotator.draw, image)
        image = await asyncio.to_thread(_downscale, image, self._max_px)
        png = await asyncio.to_thread(_to_png, image)
        return Message.user_with_image(caption, png, detail=self._detail)

    def _caption_for(self, image: Image.Image) -> str:
        """子类可基于当前画面生成动态说明。"""
        return self._caption


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
