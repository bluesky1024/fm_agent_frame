"""计算机使用通用能力：截屏、鼠标、观察与标注。

不含任何具体应用的规则；应用通过 backend/annotator 协议组合这些能力。
"""

from agent_frame.capabilities.computer_use.annotate import (
    Annotator,
    GridAnnotator,
    GridGeometry,
)
from agent_frame.capabilities.computer_use.mouse import (
    MouseBackend,
    MouseController,
    enable_dpi_awareness,
)
from agent_frame.capabilities.computer_use.observer import ScreenObserver
from agent_frame.capabilities.computer_use.screen import (
    CaptureRegion,
    MSSScreenBackend,
    ScreenBackend,
    ScreenCapture,
)

__all__ = [
    "Annotator",
    "CaptureRegion",
    "GridAnnotator",
    "GridGeometry",
    "MSSScreenBackend",
    "MouseBackend",
    "MouseController",
    "ScreenBackend",
    "ScreenCapture",
    "ScreenObserver",
    "enable_dpi_awareness",
]
