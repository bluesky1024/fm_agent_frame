"""扫雷 e2e：假 LLM + 假屏幕/鼠标后端，跑完观察→操作→胜负校验的完整循环。"""

from typing import Any, Callable

from apps.minesweeper import (
    CONCLUSION_LOST,
    CONCLUSION_WON,
    BoardGeometry,
    MinesweeperConfig,
    run_autoplay,
)
from apps.minesweeper.board_state import COVERED, FLAGGED, REVEALED
from PIL import Image, ImageDraw

from agent_frame.capabilities.computer_use import CaptureRegion, MouseController, ScreenCapture
from agent_frame.core.messages import ToolCall
from agent_frame.llm.base import ChatResult, StreamChunk

_CELL = 10
_SIZE = (110, 110)


def _playing_cells() -> dict[tuple[int, int], str]:
    return {}


def _winning_cells() -> dict[tuple[int, int], str]:
    flagged = {(1, 1), (1, 2), (1, 3)}
    return {
        (row, col): "flagged" if (row, col) in flagged else "revealed"
        for row in range(1, 10)
        for col in range(1, 10)
    }


def _near_winning_cells() -> dict[tuple[int, int], str]:
    cells = _winning_cells()
    cells[(1, 4)] = "covered"
    return cells


def _lost_cells() -> dict[tuple[int, int], str]:
    cells = _winning_cells()
    cells[(5, 5)] = "revealed"
    return cells


def _render(
    cells: dict[tuple[int, int], str], exploded: tuple[int, int] | None = None
) -> Image.Image:
    img = Image.new("RGB", _SIZE, COVERED)
    draw = ImageDraw.Draw(img)
    fills = {"revealed": REVEALED, "covered": COVERED, "flagged": FLAGGED}
    for (row, col), kind in cells.items():
        x0, y0 = (col - 1) * _CELL, (row - 1) * _CELL
        draw.rectangle([x0, y0, x0 + _CELL - 1, y0 + _CELL - 1], fill=fills[kind])
    if exploded is not None:
        row, col = exploded
        x0, y0 = (col - 1) * _CELL, (row - 1) * _CELL
        draw.line([x0 + 3, y0 + 3, x0 + 6, y0 + 6], fill=(204, 0, 0), width=1)
        draw.line([x0 + 3, y0 + 6, x0 + 6, y0 + 3], fill=(204, 0, 0), width=1)
    return img


class FakeScreenBackend:
    def __init__(
        self,
        cells: dict[tuple[int, int], str],
        *,
        exploded: tuple[int, int] | None = None,
    ) -> None:
        self.cells = cells
        self.exploded = exploded
        self.calls = 0

    def set_cells(
        self, cells: dict[tuple[int, int], str], *, exploded: tuple[int, int] | None = None
    ) -> None:
        self.cells = cells
        self.exploded = exploded

    def grab(self, region: CaptureRegion) -> Image.Image:
        self.calls += 1
        return _render(self.cells, self.exploded)


class FakeMouseBackend:
    def __init__(self, on_click: Callable[[], None] | None = None) -> None:
        self.events: list[tuple[Any, ...]] = []
        self._on_click = on_click

    def click(self, x, y, button="left"):
        self.events.append(("click", x, y, button))
        if self._on_click is not None:
            self._on_click()

    def moveTo(self, x, y):
        self.events.append(("moveTo", x, y))

    def press(self, key):
        self.events.append(("press", key))

    def keyDown(self, key):
        self.events.append(("keyDown", key))

    def keyUp(self, key):
        self.events.append(("keyUp", key))


class ScriptedLLM:
    def __init__(self, results: list[ChatResult]) -> None:
        self._results = list(results)
        self.requests: list[list[Any]] = []

    async def chat(self, messages, tools=None, *, model=None) -> ChatResult:
        raise AssertionError("runtime 应使用 stream()")

    async def stream(self, messages, tools=None, *, model=None):
        self.requests.append(list(messages))
        yield StreamChunk(result=self._results.pop(0))


def _config(max_steps: int = 10) -> MinesweeperConfig:
    return MinesweeperConfig(
        geometry=BoardGeometry(origin_x=0, origin_y=0, cell_w=_CELL, cell_h=_CELL, rows=9, cols=9),
        region=CaptureRegion(left=0, top=0, width=_SIZE[0], height=_SIZE[1]),
        mines=3,
        max_steps=max_steps,
        tool_timeout=5.0,
    )


def _backend(
    cells: dict[tuple[int, int], str],
    *,
    exploded: tuple[int, int] | None = None,
    on_click: Callable[[], None] | None = None,
) -> tuple[ScreenCapture, MouseController, FakeScreenBackend, FakeMouseBackend]:
    screen = FakeScreenBackend(cells, exploded=exploded)
    mouse = FakeMouseBackend(on_click=on_click)
    capture = ScreenCapture(_config().region, backend=screen)
    controller = MouseController(backend=mouse)
    return capture, controller, screen, mouse


def _assert_observation_is_last(messages: list[Any]) -> None:
    image_messages = [m for m in messages if isinstance(m.content, list)]
    assert len(image_messages) == 1
    assert messages[-1] is image_messages[0]


def _click(row: int, col: int, call_id: str = "c1") -> ChatResult:
    return ChatResult(
        tool_calls=[ToolCall(id=call_id, name="click_cell", arguments={"row": row, "col": col})]
    )


async def test_autoplay_observes_acts_and_stops_on_verified_win():
    llm = ScriptedLLM(
        [
            _click(1, 4),
            ChatResult(
                tool_calls=[ToolCall(id="c2", name="flag_cell", arguments={"row": 2, "col": 2})]
            ),
            ChatResult(content=CONCLUSION_WON),
        ]
    )
    screen = FakeScreenBackend(_near_winning_cells())
    mouse_backend = FakeMouseBackend(on_click=lambda: screen.set_cells(_winning_cells()))
    capture = ScreenCapture(_config().region, backend=screen)
    mouse = MouseController(backend=mouse_backend)

    result = await run_autoplay(_config(), llm, mouse=mouse, capture=capture)

    assert result.output == CONCLUSION_WON
    assert screen.calls == 4  # 三步观察 + 一次结束前校验
    assert mouse_backend.events == [
        ("click", 35, 5, "left"),
        ("keyDown", "shift"),
        ("click", 15, 15, "left"),
        ("keyUp", "shift"),
    ]
    for request in llm.requests:
        _assert_observation_is_last(request)
    assert [m.role for m in llm.requests[1]] == ["system", "user", "assistant", "tool", "user"]


async def test_autoplay_nudges_once_then_wins_on_screen():
    screen_holder: list[FakeScreenBackend] = []
    calls = {"n": 0}

    def win_after_click() -> None:
        calls["n"] += 1
        screen_holder[0].set_cells(_winning_cells())

    llm = ScriptedLLM(
        [
            ChatResult(content="请提供最新棋盘截图以便我继续判断。"),
            _click(1, 4),
            ChatResult(content="继续。"),
        ]
    )
    capture, mouse, screen, _ = _backend(_playing_cells(), on_click=win_after_click)
    screen_holder.append(screen)

    result = await run_autoplay(_config(), llm, mouse=mouse, capture=capture)

    assert calls["n"] == 1
    assert result.output == CONCLUSION_WON
    assert len(llm.requests) == 3
    assert any(
        isinstance(m.content, str) and "请继续" in m.content for m in llm.requests[1]
    )
    _assert_observation_is_last(llm.requests[1])


async def test_autoplay_rejects_false_win_and_gives_up_after_three_nudges():
    false_win = f"{CONCLUSION_WON}（所有非雷格都已翻开）"
    llm = ScriptedLLM(
        [
            ChatResult(content=false_win),
            ChatResult(content="请提供最新棋盘截图。"),
            ChatResult(content="请提供最新棋盘截图。"),
            ChatResult(content="请提供最新棋盘截图。"),
        ]
    )
    capture, mouse, _, _ = _backend(_playing_cells())

    result = await run_autoplay(_config(), llm, mouse=mouse, capture=capture)

    assert result.output.startswith("未能完成本局")
    assert len(llm.requests) == 4
    nudge = next(
        m.content
        for m in llm.requests[1]
        if isinstance(m.content, str) and "本局尚未结束" in m.content
    )
    assert "未翻开 81 格" in nudge


async def test_autoplay_does_not_require_model_conclusion_to_finish():
    llm = ScriptedLLM([ChatResult(content="我不知道下一步该点哪里。")])
    capture, mouse, _, _ = _backend(_winning_cells())

    result = await run_autoplay(_config(), llm, mouse=mouse, capture=capture)

    assert result.output == CONCLUSION_WON
    assert len(llm.requests) == 1


async def test_autoplay_detects_a_revealed_mine():
    llm = ScriptedLLM([ChatResult(content="请继续。")])
    capture, mouse, _, _ = _backend(_lost_cells(), exploded=(5, 5))

    result = await run_autoplay(_config(), llm, mouse=mouse, capture=capture)

    assert result.output == CONCLUSION_LOST


async def test_autoplay_does_not_nudge_after_framework_error():
    llm = ScriptedLLM([_click(1, 1)])
    capture, mouse, _, _ = _backend(_playing_cells())

    result = await run_autoplay(_config(max_steps=1), llm, mouse=mouse, capture=capture)

    assert len(llm.requests) == 1
    assert result.output == ""
