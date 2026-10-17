"""扫雷 Agent 的组装：系统提示词、工具注册与运行时 spec。

观察帧通过 ContextProvider 每次装配时实时获取：历史里只保留文本进展，
不发旧截图（与旧 Observer 的「当前帧」语义一致）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_frame.context import ContextProvider, ContextRequest
from agent_frame.core.messages import Message
from agent_frame.core.types import AgentResult
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController
from agent_frame.desktop.observer import BoardObserver
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture
from agent_frame.interfaces.session import InMemorySession
from agent_frame.runtime import AgentRuntime, AgentSpec
from agent_frame.tools import ToolRegistry
from agent_frame.tools.desktop import ClickCellTool, FlagCellTool, RestartGameTool

SYSTEM_PROMPT = """你是一个扫雷专家，通过截图观察棋盘并操作鼠标通关。

每轮你会收到一张最新棋盘截图，格子外侧标注了 1 基行列号（行自上而下、列自左而右）。
棋盘上：数字表示该格周围 8 格的雷数；空白表示周围无雷；旗子表示你标记的雷。

可用工具：
- click_cell(row, col)：翻开一个格子（确定它安全时）。
- flag_cell(row, col)：给一个格子插旗（确定它是雷时）。
- restart_game()：仅当本局已结束（胜利，或已踩到雷）时调用，重开新局。

规则：
- 每轮把当前所有能确定的动作一次性做完：确定的雷全部 flag_cell，确定安全的格子全部 click_cell。
- 不要一轮只做一个动作；也不要把本可确定的动作留到下一轮。
- 只依据最新截图决策，不要重复操作已经翻开的格子。
- 直接调用工具，不要输出任何解释、推理或思考过程。
- 无法确定时，选择最可能安全的格子翻开（不要乱猜高风险格）。
- 本局结束时必须调用 restart_game 开新局，继续游戏。"""


class ObserverContextProvider:
    """每轮装配时抓一帧最新观察，作为请求视图的一部分（不写回历史）。"""

    def __init__(self, observer: BoardObserver) -> None:
        self._observer = observer

    async def provide(self, request: ContextRequest) -> list[Message]:
        return [await self._observer.observe()]


@dataclass
class MinesweeperAgent:
    """应用层组合：运行时 + spec + 会话。"""

    runtime: AgentRuntime
    spec: AgentSpec
    session: InMemorySession

    async def run(self, task: str) -> AgentResult:
        return await self.runtime.run_collect(self.spec, self.session, task)


def build_registry(config: dict[str, Any], mouse: MouseController) -> ToolRegistry:
    geometry = BoardGeometry(**config["geometry"])
    restart = config["restart"]
    if restart["type"] == "click":
        restart_tool = RestartGameTool(mouse, click_xy=(restart["x"], restart["y"]))
    else:
        restart_tool = RestartGameTool(mouse, key=restart["key"])
    return ToolRegistry(
        [ClickCellTool(geometry, mouse), FlagCellTool(geometry, mouse), restart_tool]
    )


def build_agent(
    config: dict[str, Any],
    llm: Any,
    *,
    mouse: MouseController | None = None,
    capture: ScreenCapture | None = None,
    session_id: str = "minesweeper",
) -> MinesweeperAgent:
    geometry = BoardGeometry(**config["geometry"])
    region = CaptureRegion(**config["region"])
    mouse = mouse or MouseController()
    capture = capture or ScreenCapture(region)
    observer = BoardObserver(
        capture,
        geometry,
        detail=config.get("image_detail", "high"),
        max_px=config.get("image_max_px", 1300),
    )
    registry = build_registry(config, mouse)
    provider: ContextProvider = ObserverContextProvider(observer)
    spec = AgentSpec(
        llm=llm,
        name="minesweeper",
        system_prompt=SYSTEM_PROMPT,
        tools=registry.tools(),
        context_providers=[provider],
        max_steps=config.get("max_steps", 300),
        tool_timeout=config.get("tool_timeout", 30.0),
    )
    return MinesweeperAgent(
        runtime=AgentRuntime(),
        spec=spec,
        session=InMemorySession(id=session_id),
    )
