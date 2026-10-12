"""鼠标与按键控制（基于 pyautogui），以及 Windows 高 DPI 对齐。"""

from __future__ import annotations

import sys
from typing import Protocol


class InputBackend(Protocol):
    """pyautogui 所需的最小接口；测试用 fake 实现。

    注意 button 必须按关键字传递：pyautogui.click 的第 3 个位置参数是 clicks
    （点击次数）而非 button，位置传参会把按钮名当成次数而报错。
    """

    def click(self, x: int, y: int, button: str = "left") -> None: ...
    def moveTo(self, x: int, y: int) -> None: ...
    def press(self, key: str) -> None: ...


def enable_dpi_awareness() -> None:
    """Windows 高 DPI 下让屏幕坐标对齐物理像素；非 Windows 为 no-op。

    必须在使用坐标点击前调用，否则缩放会把点击位置带偏。
    """
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
    except Exception:  # noqa: BLE001 - 老系统回退到 system DPI aware
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


class MouseController:
    """把点击/移动/按键转发给底层后端（默认 pyautogui）。"""

    def __init__(self, backend: InputBackend | None = None) -> None:
        self._backend = backend or _default_backend()

    def click(self, x: int, y: int, *, button: str = "left") -> None:
        self._backend.click(x, y, button=button)

    def move_to(self, x: int, y: int) -> None:
        self._backend.moveTo(x, y)

    def press(self, key: str) -> None:
        self._backend.press(key)


def _default_backend() -> InputBackend:
    import pyautogui  # 延迟导入，避免测试环境需要 GUI 依赖

    return pyautogui
