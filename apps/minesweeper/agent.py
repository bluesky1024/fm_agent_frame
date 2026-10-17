"""扫雷 Agent 组装：工具注册、观察提供者与 AgentSpec。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_frame.capabilities.computer_use import MouseController, ScreenCapture, ScreenObserver
from agent_frame.context import ContextProvider, ContextRequest
from agent_frame.core.messages import Message
from agent_frame.core.types import AgentResult
from agent_frame.interfaces.session import InMemorySession
from agent_frame.runtime import AgentRuntime, AgentSpec
from agent_frame.tools import ToolRegistry
from apps.minesweeper.board_state import BoardProbe
from apps.minesweeper.config import MinesweeperConfig
from apps.minesweeper.observer import BoardObserver
from apps.minesweeper.prompt import build_system_prompt
from apps.minesweeper.tools import ClickCellTool, FlagCellTool


class ObserverContextProvider:
    """每轮装配时抓一帧最新观察，追加在历史之后（不写回历史）。"""

    placement = "after_history"

    def __init__(self, observer: ScreenObserver) -> None:
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


def build_registry(
    config: MinesweeperConfig,
    mouse: MouseController,
    *,
    probe: BoardProbe | None = None,
) -> ToolRegistry:
    return ToolRegistry(
        [
            ClickCellTool(config.geometry, mouse, probe=probe),
            FlagCellTool(config.geometry, mouse),
        ]
    )


def build_agent(
    config: MinesweeperConfig,
    llm: Any,
    *,
    mouse: MouseController | None = None,
    capture: ScreenCapture | None = None,
    session_id: str = "minesweeper",
) -> MinesweeperAgent:
    mouse = mouse or MouseController()
    capture = capture or ScreenCapture(config.region)
    observer = BoardObserver(
        capture,
        config.geometry,
        mines=config.mines,
        detail=config.image_detail,
        max_px=config.image_max_px,
    )
    probe = BoardProbe(lambda: observer.last_image, observer.image_geometry)
    registry = build_registry(config, mouse, probe=probe)
    provider: ContextProvider = ObserverContextProvider(observer)
    spec = AgentSpec(
        llm=llm,
        name="minesweeper",
        model=None,
        system_prompt=build_system_prompt(
            config.mines, config.geometry.rows * config.geometry.cols
        ),
        tools=registry.tools(),
        context_providers=[provider],
        max_steps=config.max_steps,
        tool_timeout=config.tool_timeout,
    )
    return MinesweeperAgent(
        runtime=AgentRuntime(),
        spec=spec,
        session=InMemorySession(id=session_id),
    )
