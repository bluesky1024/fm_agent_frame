"""截屏：把屏幕上一块矩形区域抓成 PIL 图像。

返回的图像始终与鼠标/屏幕逻辑坐标 1:1 对应：当底层截屏库返回物理像素
（如 macOS Retina 2x 或 Windows 未 DPI-aware）时，grab() 会按 scale
把图像归一化回逻辑尺寸。

``ScreenBackend`` 是外部边界协议，测试可注入假实现。
"""

from __future__ import annotations

from typing import Protocol

from PIL import Image
from pydantic import BaseModel


class CaptureRegion(BaseModel):
    """截屏区域（屏幕逻辑坐标）。"""

    left: int
    top: int
    width: int
    height: int


class ScreenBackend(Protocol):
    """截屏后端：抓取给定区域并返回 PIL 图像。"""

    def grab(self, region: CaptureRegion) -> Image.Image: ...


class MSSScreenBackend:
    """默认后端：用 mss 抓取屏幕区域。"""

    def grab(self, region: CaptureRegion) -> Image.Image:
        import mss

        with mss.MSS() as sct:
            shot = sct.grab(
                {
                    "left": region.left,
                    "top": region.top,
                    "width": region.width,
                    "height": region.height,
                }
            )
            return Image.frombytes("RGB", shot.size, shot.rgb)


class ScreenCapture:
    """按区域截屏，并处理物理像素与逻辑坐标的缩放。"""

    def __init__(
        self,
        region: CaptureRegion,
        backend: ScreenBackend | None = None,
        *,
        scale: float | None = None,
    ) -> None:
        self._region = region
        self._backend = backend or MSSScreenBackend()
        if scale is not None:
            self._scale = scale
        elif backend is not None:
            self._scale = 1.0
        else:
            self._scale = None  # 生产路径：首次 grab 时探测

    @property
    def region(self) -> CaptureRegion:
        return self._region

    def grab(self) -> Image.Image:
        scale = self._scale
        if scale is None:
            scale = _detect_scale()
            self._scale = scale
        if scale == 1.0:
            return self._backend.grab(self._region)
        left = round(self._region.left * scale)
        top = round(self._region.top * scale)
        right = round((self._region.left + self._region.width) * scale)
        bottom = round((self._region.top + self._region.height) * scale)
        physical = CaptureRegion(
            left=left,
            top=top,
            width=right - left,
            height=bottom - top,
        )
        img = self._backend.grab(physical)
        return img.resize((self._region.width, self._region.height))


def _detect_scale() -> float:
    """探测 mss 物理像素与逻辑点的比值（取主屏）。"""
    import mss
    import pyautogui

    with mss.MSS() as sct:
        mss_w = sct.monitors[1]["width"]
    logical_w = pyautogui.size().width
    return round(mss_w / logical_w, 3) if logical_w else 1.0
