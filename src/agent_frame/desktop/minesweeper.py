"""扫雷 Agent 的组装：系统提示词、配置加载、工具注册与 Agent 构建。"""

from __future__ import annotations

import json
from pathlib import Path

from agent_frame.agent import ToolUseAgent
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController
from agent_frame.desktop.observer import BoardObserver
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture
from agent_frame.tools import ToolRegistry
from agent_frame.tools.desktop import ClickCellTool, FlagCellTool, RestartGameTool

SYSTEM_PROMPT = """你是一个扫雷专家，正在通过截图观察一款扫雷游戏并操作鼠标通关。

每一轮你都会收到一张最新棋盘截图，格子外侧标注了行列号（1 基：行自上而下、列自左而右）。
棋盘上：数字表示该格周围 8 格的雷数；空白表示周围无雷；带旗帜的格子是你已标记的雷。

可用工具：
- click_cell(row, col)：翻开一个格子（当你确定它安全时）。
- flag_cell(row, col)：插旗标记一个格子为雷。
- restart_game()：仅当本局已经结束（胜利，或已踩到雷）时调用，重开新局。

策略：
- 若某数字等于其周围未翻开格数量，则这些未翻开格全是雷，用 flag_cell 全部插旗。
- 若某数字等于其周围已插旗数量，则其余未翻开格安全，用 click_cell 全部翻开。
- 无法确定时，选择周围约束下最可能安全的格子翻开（不要乱猜高风险格）。
- 一轮里可以批量输出多个确定的动作以节省开销。
- 每步只依据最新截图决策；看不到进展时优先做确定性的翻开/插旗。

注意：本局结束时必须调用 restart_game 开新局，继续游戏。"""


def load_config(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_registry(config: dict, mouse: MouseController) -> ToolRegistry:
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
    config: dict,
    llm,
    *,
    mouse: MouseController | None = None,
    capture: ScreenCapture | None = None,
) -> ToolUseAgent:
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
    return ToolUseAgent(
        llm,
        registry,
        system_prompt=SYSTEM_PROMPT,
        max_steps=config.get("max_steps", 300),
        observer=observer,
    )
