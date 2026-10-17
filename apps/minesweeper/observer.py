"""扫雷观察：截屏 + 网格标注，组装成带图 user 消息。"""

from __future__ import annotations

from agent_frame.capabilities.computer_use import GridAnnotator, ScreenCapture, ScreenObserver
from apps.minesweeper.board import BoardGeometry

_DEFAULT_CAPTION = (
    "这是当前扫雷棋盘的截图，每个格子外侧已标注 1 基行列号。请根据棋盘状态决定下一步动作。"
)


class BoardObserver(ScreenObserver):
    """把屏幕坐标几何平移到截屏图像坐标后画网格。"""

    def __init__(
        self,
        capture: ScreenCapture,
        geometry: BoardGeometry,
        *,
        detail: str = "high",
        max_px: int = 1300,
        caption: str = _DEFAULT_CAPTION,
    ) -> None:
        offset = geometry.translated(-capture.region.left, -capture.region.top)
        super().__init__(
            capture,
            annotator=GridAnnotator(offset),
            caption=caption,
            detail=detail,
            max_px=max_px,
        )
