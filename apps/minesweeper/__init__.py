"""扫雷应用：棋盘几何、工具、观察、提示词与启动逻辑。"""

from apps.minesweeper.agent import MinesweeperAgent, build_agent, build_registry
from apps.minesweeper.board import BoardGeometry
from apps.minesweeper.config import MinesweeperConfig
from apps.minesweeper.launcher import GAME_PATH, launch_game, run_autoplay
from apps.minesweeper.observer import BoardObserver
from apps.minesweeper.outcome import CONCLUSION_LOST, CONCLUSION_WON, parse_conclusion
from apps.minesweeper.prompt import build_system_prompt
from apps.minesweeper.tools import ClickCellTool, FlagCellTool

__all__ = [
    "BoardGeometry",
    "BoardObserver",
    "ClickCellTool",
    "FlagCellTool",
    "GAME_PATH",
    "MinesweeperAgent",
    "MinesweeperConfig",
    "CONCLUSION_LOST",
    "CONCLUSION_WON",
    "build_agent",
    "build_system_prompt",
    "build_registry",
    "launch_game",
    "parse_conclusion",
    "run_autoplay",
]
