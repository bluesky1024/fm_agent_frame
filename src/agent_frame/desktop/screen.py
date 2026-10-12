"""截屏：把屏幕上一块矩形区域抓成 PIL 图像。

返回的图像始终与 pyautogui 屏幕坐标 1:1 对应：当底层截屏库返回
物理像素（如 macOS Retina 2x 或 Windows 未 DPI-aware）时，grab()
会按 scale 把图像归一化回逻辑尺寸。
"""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image
from pydantic import BaseModel


class CaptureRegion(BaseModel):
    """截屏区域（屏幕坐标）。"""

    left: int
    top: int
    width: int
    height: int


Grabber = Callable[[CaptureRegion], Image.Image]


class ScreenCapture:
    """按区域截屏。默认用 mss；测试可注入 grabber。

    scale 是「mss 物理像素 / pyautogui 逻辑点」的比值：
    - 生产（无 grabber、无 scale）：首次 grab() 惰性探测并缓存。
    - 注入 grabber 且未显式传 scale：视为 1.0（grabber 返回的即屏幕坐标图）。
    - 显式传 scale：可测试归一化行为。
    """

    def __init__(
        self,
        region: CaptureRegion,
        grabber: Grabber | None = None,
        *,
        scale: float | None = None,
    ) -> None:
        self._region = region
        self._grab = grabber or _default_grabber
        if scale is not None:
            self._scale = scale
        elif grabber is not None:
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
            return self._grab(self._region)
        left = round(self._region.left * scale)
        top = round(self._region.top * scale)
        right = round((self._region.left + self._region.width) * scale)
        bottom = round((self._region.top + self._region.height) * scale)
        mss_region = CaptureRegion(
            left=left,
            top=top,
            width=right - left,
            height=bottom - top,
        )
        img = self._grab(mss_region)
        return img.resize((self._region.width, self._region.height))


def _detect_scale() -> float:
    """探测 mss 物理像素与 pyautogui 逻辑点的比值（取主屏）。"""
    import mss
    import pyautogui

    with mss.MSS() as sct:
        mss_w = sct.monitors[1]["width"]
    logical_w = pyautogui.size().width
    return round(mss_w / logical_w, 3) if logical_w else 1.0


def _default_grabber(region: CaptureRegion) -> Image.Image:
    import mss  # 延迟导入，避免测试环境需要截屏依赖

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
