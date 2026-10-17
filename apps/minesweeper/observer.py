"""扫雷观察：截屏 + 网格标注，组装成带图 user 消息。"""

from __future__ import annotations

from PIL import Image

from agent_frame.capabilities.computer_use import GridAnnotator, ScreenCapture, ScreenObserver
from apps.minesweeper.board import BoardGeometry
from apps.minesweeper.board_state import analyze_board

_DEFAULT_CAPTION = (
    "这是本轮刚截取的最新扫雷棋盘截图（位于对话末尾，代表当前状态），"
    "每个格子外侧已标注 1 基行列号。请根据棋盘状态决定下一步动作。"
)


class BoardObserver(ScreenObserver):
    """把屏幕坐标几何平移到截屏图像坐标后画网格，并附上实时计数。"""

    def __init__(
        self,
        capture: ScreenCapture,
        geometry: BoardGeometry,
        *,
        mines: int,
        detail: str = "high",
        max_px: int = 1300,
        caption: str = _DEFAULT_CAPTION,
    ) -> None:
        self._image_geometry = geometry.translated(
            -capture.region.left, -capture.region.top
        )
        self._mines = mines
        super().__init__(
            capture,
            annotator=GridAnnotator(self._image_geometry),
            caption=caption,
            detail=detail,
            max_px=max_px,
        )

    @property
    def image_geometry(self) -> BoardGeometry:
        return self._image_geometry

    def _caption_for(self, image: Image.Image) -> str:
        state = analyze_board(image, self._image_geometry)
        target = state.total - self._mines
        return (
            f"{self._caption} 当前计数：{state.describe()}；"
            f"本局共 {self._mines} 颗雷，已翻开 {target} 格才算胜利。"
        )
