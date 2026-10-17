"""启动目标扫雷程序并跑一局自动对局。

``games/minesweeper.py`` 是被操作的目标程序，本应用不修改它。
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent_frame.capabilities.computer_use import MouseController, ScreenCapture
from agent_frame.core.events import Error, RunEnd
from agent_frame.core.types import AgentResult
from apps.minesweeper.agent import MinesweeperAgent, build_agent
from apps.minesweeper.board_state import BoardState, analyze_board
from apps.minesweeper.config import MinesweeperConfig
from apps.minesweeper.outcome import (
    CONCLUSION_LOST,
    CONCLUSION_WON,
    parse_conclusion,
)

GAME_PATH = Path(__file__).resolve().parents[2] / "games" / "minesweeper.py"

TASK = "赢下这局扫雷。"
MAX_TEXT_ONLY_NUDGES = 3


def launch_game() -> subprocess.Popen[bytes]:
    return subprocess.Popen([sys.executable, str(GAME_PATH)])


async def run_autoplay(
    config: MinesweeperConfig,
    llm: Any,
    *,
    mouse: MouseController | None = None,
    capture: ScreenCapture | None = None,
) -> AgentResult:
    """跑一局。

    模型只负责操作与给出结束结论；胜负由应用层直接读截图确认，
    避免模型在棋盘尚未结束时误报胜利。
    """
    capture = capture or ScreenCapture(config.region)
    agent = build_agent(config, llm, mouse=mouse, capture=capture)
    result, failed = await _run_once(agent, TASK)
    nudges = 0
    while True:
        state = await _observe_state(config, capture)
        if state.is_lost():
            return _with_output(result, CONCLUSION_LOST)
        if state.is_won(config.mines):
            return _with_output(result, CONCLUSION_WON)
        if failed:
            return result
        if nudges >= MAX_TEXT_ONLY_NUDGES:
            return _protocol_failure(result, state, config.mines)
        nudges += 1
        prompt = _continue_prompt(state, config.mines, result.output)
        result, failed = await _run_once(agent, prompt)


async def _run_once(agent: MinesweeperAgent, task: str) -> tuple[AgentResult, bool]:
    """跑一次 runtime，返回最终结果以及是否以框架错误收尾。"""
    result = AgentResult(output="")
    failed = False
    async for event in agent.runtime.run(agent.spec, agent.session, task):
        if isinstance(event, RunEnd):
            result = event.result
        elif isinstance(event, Error):
            failed = True
    return result, failed


async def _observe_state(config: MinesweeperConfig, capture: ScreenCapture) -> BoardState:
    image = await asyncio.to_thread(capture.grab)
    geometry = config.geometry.translated(-config.region.left, -config.region.top)
    return analyze_board(image, geometry)


def _with_output(result: AgentResult, output: str) -> AgentResult:
    return result.model_copy(update={"output": output})


def _continue_prompt(state: BoardState, mines: int, last_output: str) -> str:
    claimed = parse_conclusion(last_output)
    reason = (
        f"你最后输出的是“{claimed}”，但截图显示本局尚未结束。"
        if claimed is not None
        else "请继续。"
    )
    return (
        f"{reason}当前棋盘：{state.describe()}；本局共 {mines} 颗雷。"
        "你每轮只能二选一：调用工具继续游戏；或在本局确实结束时，"
        f"不调用任何工具，单独输出一行“{CONCLUSION_WON}”或“{CONCLUSION_LOST}”。"
        "不要输出其他内容。"
    )


def _protocol_failure(result: AgentResult, state: BoardState, mines: int) -> AgentResult:
    return _with_output(
        result,
        (
            f"未能完成本局：连续 {MAX_TEXT_ONLY_NUDGES} 次追加提示后，"
            f"模型仍未调用工具。当前棋盘：{state.describe()}；本局共 {mines} 颗雷。"
            f"最后输出：{result.output}"
        ),
    )
