"""扫雷应用：棋盘几何、工具、观察、提示词与启动逻辑。"""

from apps.minesweeper.agent import MinesweeperAgent, build_agent, build_registry
from apps.minesweeper.board import BoardGeometry
from apps.minesweeper.config import MinesweeperConfig, RestartSpec
from apps.minesweeper.launcher import GAME_PATH, launch_game, run_autoplay
from apps.minesweeper.observer import BoardObserver
from apps.minesweeper.prompt import SYSTEM_PROMPT
from apps.minesweeper.tools import ClickCellTool, FlagCellTool, RestartGameTool

__all__ = [
    "BoardGeometry",
    "BoardObserver",
    "ClickCellTool",
    "FlagCellTool",
    "GAME_PATH",
    "MinesweeperAgent",
    "MinesweeperConfig",
    "RestartGameTool",
    "RestartSpec",
    "SYSTEM_PROMPT",
    "build_agent",
    "build_registry",
    "launch_game",
    "run_autoplay",
]
