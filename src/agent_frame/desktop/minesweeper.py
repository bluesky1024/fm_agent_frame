"""扫雷 Agent 的组装：系统提示词、工具注册与 Agent 构建。"""

from __future__ import annotations

from agent_frame.agent import ToolUseAgent
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController
from agent_frame.desktop.observer import BoardObserver
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture
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
