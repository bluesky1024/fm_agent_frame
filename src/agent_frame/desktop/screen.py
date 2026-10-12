"""截屏：把屏幕上一块矩形区域抓成 PIL 图像。"""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image
from pydantic import BaseModel


class CaptureRegion(BaseModel):
    """截屏区域（屏幕绝对像素）。"""

    left: int
    top: int
    width: int
    height: int


Grabber = Callable[[CaptureRegion], Image.Image]


class ScreenCapture:
    """按区域截屏。默认用 mss；测试可注入 grabber。"""

    def __init__(self, region: CaptureRegion, grabber: Grabber | None = None) -> None:
        self._region = region
        self._grab = grabber or _default_grabber

    @property
    def region(self) -> CaptureRegion:
        return self._region

    def grab(self) -> Image.Image:
        return self._grab(self._region)


def _default_grabber(region: CaptureRegion) -> Image.Image:
    import mss  # 延迟导入，避免测试环境需要截屏依赖

    with mss.mss() as sct:
        shot = sct.grab(
            {
                "left": region.left,
                "top": region.top,
                "width": region.width,
                "height": region.height,
            }
        )
        return Image.frombytes("RGB", shot.size, shot.rgb)
