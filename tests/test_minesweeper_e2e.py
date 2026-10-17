"""扫雷 e2e：假 LLM + 假屏幕/鼠标后端，跑完启动→观察→操作→结束。"""

from typing import Any

from apps.minesweeper import (
    BoardGeometry,
    MinesweeperConfig,
    RestartSpec,
    build_agent,
)
from PIL import Image

from agent_frame.capabilities.computer_use import CaptureRegion, MouseController, ScreenCapture
from agent_frame.core.events import AgentEvent
from agent_frame.core.messages import ToolCall
from agent_frame.llm.base import ChatResult, StreamChunk


class FakeScreenBackend:
    def __init__(self) -> None:
        self.calls = 0

    def grab(self, region: CaptureRegion) -> Image.Image:
        self.calls += 1
        return Image.new("RGB", (region.width, region.height), "white")


class FakeMouseBackend:
    def __init__(self) -> None:
        self.events: list[tuple[Any, ...]] = []

    def click(self, x, y, button="left"):
        self.events.append(("click", x, y, button))

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

    async def chat(self, messages, tools=None) -> ChatResult:
        raise AssertionError("runtime 应使用 stream()")

    async def stream(self, messages, tools=None):
        yield StreamChunk(result=self._results.pop(0))


def _config() -> MinesweeperConfig:
    return MinesweeperConfig(
        geometry=BoardGeometry(origin_x=0, origin_y=0, cell_w=10, cell_h=10, rows=9, cols=9),
        region=CaptureRegion(left=0, top=0, width=110, height=110),
        restart=RestartSpec(kind="click", x=50, y=50),
        max_steps=10,
        tool_timeout=5.0,
    )


async def test_fake_llm_and_fake_backends_complete_a_game_loop() -> None:
    llm = ScriptedLLM(
        [
            ChatResult(
                tool_calls=[ToolCall(id="c1", name="click_cell", arguments={"row": 1, "col": 1})]
            ),
            ChatResult(
                tool_calls=[ToolCall(id="c2", name="flag_cell", arguments={"row": 2, "col": 2})]
            ),
            ChatResult(tool_calls=[ToolCall(id="c3", name="restart_game", arguments={})]),
            ChatResult(content="本局结束"),
        ]
    )
    screen = FakeScreenBackend()
    mouse = FakeMouseBackend()
    agent = build_agent(
        _config(),
        llm,
        mouse=MouseController(backend=mouse),
        capture=ScreenCapture(_config().region, backend=screen),
    )

    events: list[AgentEvent] = [
        event async for event in agent.runtime.run(agent.spec, agent.session, "赢下这局")
    ]

    assert events[0].type == "run_start"
    assert events[-1].type == "run_end"
    assert sum(1 for e in events if e.type == "tool_result") == 3
    assert getattr(events[-1], "result").output == "本局结束"

    # 观察：首帧 + 每批工具后各一帧
    assert screen.calls == 4
    # 操作：翻格、Shift+插旗、重开
    assert mouse.events == [
        ("click", 5, 5, "left"),
        ("keyDown", "shift"),
        ("click", 15, 15, "left"),
        ("keyUp", "shift"),
        ("click", 50, 50, "left"),
    ]

    # 历史只保留文本进展，不带屏幕截图
    assert [m.role for m in agent.session.history] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
    ]
    assert all(not isinstance(m.content, list) for m in agent.session.history)
