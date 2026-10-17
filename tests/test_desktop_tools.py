import pytest
from apps.minesweeper.board import BoardGeometry
from apps.minesweeper.tools import ClickCellTool, FlagCellTool

from agent_frame.capabilities.computer_use.mouse import MouseController
from agent_frame.core.errors import ToolError


class FakeBackend:
    """签名模拟真实 pyautogui.click（第 3 个位置参数是 clicks，不是 button）。"""

    def __init__(self) -> None:
        self.clicks = []
        self.presses = []
        self.events = []

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
        self.events.append(("click", x, y, button))

    def moveTo(self, x, y):
        pass

    def press(self, key):
        self.presses.append(key)

    def keyDown(self, key):
        self.events.append(("keyDown", key))

    def keyUp(self, key):
        self.events.append(("keyUp", key))


def _geo() -> BoardGeometry:
    return BoardGeometry(origin_x=0, origin_y=0, cell_w=10, cell_h=10, rows=9, cols=9)


async def test_click_cell_clicks_cell_center():
    b = FakeBackend()
    tool = ClickCellTool(_geo(), MouseController(backend=b))
    out = await tool.run(row=2, col=3)
    assert b.clicks == [(25, 15, "left")]
    assert out == "ok"


class FakeProbe:
    def __init__(self, state: str) -> None:
        self.state = state
        self.calls: list[tuple[int, int]] = []

    def cell_state(self, row: int, col: int) -> str:
        self.calls.append((row, col))
        return self.state


async def test_click_cell_rejects_revealed_cell():
    b = FakeBackend()
    tool = ClickCellTool(_geo(), MouseController(backend=b), probe=FakeProbe("revealed"))

    with pytest.raises(ToolError) as excinfo:
        await tool.run(row=2, col=3)

    assert excinfo.value.recoverable is True
    assert "已经翻开" in str(excinfo.value)
    assert b.clicks == []


async def test_click_cell_rejects_flagged_cell():
    b = FakeBackend()
    tool = ClickCellTool(_geo(), MouseController(backend=b), probe=FakeProbe("flagged"))

    with pytest.raises(ToolError) as excinfo:
        await tool.run(row=2, col=3)

    assert excinfo.value.recoverable is True
    assert "已插旗" in str(excinfo.value)
    assert b.clicks == []


async def test_click_cell_allows_retry_while_cell_is_still_covered():
    # 上一次点击可能因窗口未处理而丢失；只要截图仍显示未翻开，就必须允许重试
    b = FakeBackend()
    tool = ClickCellTool(_geo(), MouseController(backend=b), probe=FakeProbe("covered"))

    await tool.run(row=2, col=3)
    await tool.run(row=2, col=3)

    assert b.clicks == [(25, 15, "left"), (25, 15, "left")]


async def test_flag_cell_shift_clicks_cell_center():
    b = FakeBackend()
    tool = FlagCellTool(_geo(), MouseController(backend=b))
    out = await tool.run(row=1, col=1)
    assert b.events == [
        ("keyDown", "shift"),
        ("click", 5, 5, "left"),
        ("keyUp", "shift"),
    ]
    assert out == "ok"


