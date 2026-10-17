"""启动目标扫雷程序并跑一局自动对局。

``games/minesweeper.py`` 是被操作的目标程序，本应用不修改它。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from agent_frame.capabilities.computer_use import MouseController, ScreenCapture
from agent_frame.core.types import AgentResult
from apps.minesweeper.agent import build_agent
from apps.minesweeper.config import MinesweeperConfig

GAME_PATH = Path(__file__).resolve().parents[2] / "games" / "minesweeper.py"


def launch_game() -> subprocess.Popen[bytes]:
    return subprocess.Popen([sys.executable, str(GAME_PATH)])


async def run_autoplay(
    config: MinesweeperConfig,
    llm: Any,
    *,
    mouse: MouseController | None = None,
    capture: ScreenCapture | None = None,
) -> AgentResult:
    agent = build_agent(config, llm, mouse=mouse, capture=capture)
    return await agent.run("赢下这局扫雷。")
