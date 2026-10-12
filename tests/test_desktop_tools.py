import pytest

from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController
from agent_frame.tools.desktop import ClickCellTool, FlagCellTool, RestartGameTool


class FakeBackend:
    """签名模拟真实 pyautogui.click（第 3 个位置参数是 clicks，不是 button）。"""

    def __init__(self) -> None:
        self.clicks = []
        self.presses = []

    def click(
        self,
        x=None,
        y=None,
        clicks=1,
        interval=0.0,
        button="primary",
        duration=0.0,
        tween=None,
        logScreenshot=None,
        _pause=True,
    ):
        self.clicks.append((x, y, button))

    def moveTo(self, x, y):
        pass

    def press(self, key):
        self.presses.append(key)


def _geo() -> BoardGeometry:
    return BoardGeometry(origin_x=0, origin_y=0, cell_w=10, cell_h=10, rows=9, cols=9)


async def test_click_cell_clicks_cell_center():
    b = FakeBackend()
    tool = ClickCellTool(_geo(), MouseController(backend=b))
    out = await tool.run(row=2, col=3)
    assert b.clicks == [(25, 15, "left")]
    assert "2, 3" in out


async def test_flag_cell_right_clicks_cell_center():
    b = FakeBackend()
    tool = FlagCellTool(_geo(), MouseController(backend=b))
    out = await tool.run(row=1, col=1)
    assert b.clicks == [(5, 5, "right")]
    assert "1, 1" in out


async def test_restart_game_by_click():
    b = FakeBackend()
    tool = RestartGameTool(MouseController(backend=b), click_xy=(100, 100))
    out = await tool.run()
    assert b.clicks == [(100, 100, "left")]
    assert "100" in out


async def test_restart_game_by_key():
    b = FakeBackend()
    tool = RestartGameTool(MouseController(backend=b), key="f2")
    out = await tool.run()
    assert b.presses == ["f2"]
    assert "f2" in out


def test_restart_game_requires_exactly_one_action():
    with pytest.raises(Exception):
        RestartGameTool(MouseController(backend=FakeBackend()))
    with pytest.raises(Exception):
        RestartGameTool(
            MouseController(backend=FakeBackend()), click_xy=(1, 1), key="f2"
        )
