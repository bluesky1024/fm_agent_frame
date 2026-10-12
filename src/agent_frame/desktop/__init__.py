"""桌面自动化：截屏、鼠标控制、棋盘几何与网格标注。"""

from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController, enable_dpi_awareness
from agent_frame.desktop.observer import BoardObserver
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture

__all__ = [
    "BoardGeometry",
    "BoardObserver",
    "CaptureRegion",
    "GridAnnotator",
    "MouseController",
    "ScreenCapture",
    "enable_dpi_awareness",
]
