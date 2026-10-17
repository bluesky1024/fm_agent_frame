"""鼠标与按键控制（基于 pyautogui），以及 Windows 高 DPI 对齐。

``MouseBackend`` 是外部边界协议，测试可注入假实现。
"""

from __future__ import annotations

import sys
import threading
from typing import Protocol


class MouseBackend(Protocol):
    """pyautogui 所需的最小接口；测试用 fake 实现。

    注意 button 必须按关键字传递：pyautogui.click 的第 3 个位置参数是 clicks
    （点击次数）而非 button，位置传参会把按钮名当成次数而报错。
    """

    def click(self, x: int, y: int, button: str = "left") -> None: ...
    def moveTo(self, x: int, y: int) -> None: ...
    def press(self, key: str) -> None: ...
    def keyDown(self, key: str) -> None: ...
    def keyUp(self, key: str) -> None: ...


def enable_dpi_awareness() -> None:
    """Windows 高 DPI 下让屏幕坐标对齐物理像素；非 Windows 为 no-op。"""
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

    def __init__(self, backend: MouseBackend | None = None) -> None:
        self._backend = backend or _default_backend()
        # 工具批次会并行执行（asyncio.gather + to_thread）；pyautogui 的全局
        # 鼠标状态不是线程安全的，Shift 与普通点击交错会把普通点击变成插旗。
        self._lock = threading.Lock()

    def click(self, x: int, y: int, *, button: str = "left") -> None:
        with self._lock:
            self._backend.click(x, y, button=button)

    def move_to(self, x: int, y: int) -> None:
        with self._lock:
            self._backend.moveTo(x, y)

    def press(self, key: str) -> None:
        with self._lock:
            self._backend.press(key)

    def shift_click(self, x: int, y: int, *, button: str = "left") -> None:
        """按住 Shift 再点击；整个过程持有锁，异常时也保证释放 Shift。"""
        with self._lock:
            self._backend.keyDown("shift")
            try:
                self._backend.click(x, y, button=button)
            finally:
                self._backend.keyUp("shift")


def _default_backend() -> MouseBackend:
    import pyautogui  # 延迟导入，避免测试环境需要 GUI 依赖

    return pyautogui
