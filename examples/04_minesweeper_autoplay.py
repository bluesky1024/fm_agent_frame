"""示例 4：自研 tkinter 扫雷 + 视觉 Agent 自动对局（跨平台）。

启动 games/minesweeper.py（一个固定位置、固定格子的无边框扫雷窗口），
用游戏自报的精确坐标跑扫雷视觉 Agent，全程自动「看 → 点 → 再看」。

运行：
    MODEL=deepseek-flash python examples/04_minesweeper_autoplay.py
前提：
    - 已设置 DEEPSEEK_API_KEY（环境变量或 .env）。
    - macOS 需在「系统设置 → 隐私与安全性 → 辅助功能」授权终端/Python 控制鼠标。
停止：Ctrl+C。
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from agent_frame.capabilities.computer_use import enable_dpi_awareness
from agent_frame.core.config import get_settings
from agent_frame.llm import OpenAICompatProvider
from agent_frame.obs import setup_logging

# apps/ 与 games/ 不在已安装的包里（打包只收 src/）：直接运行本脚本时把仓库根加入 sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.minesweeper import MinesweeperConfig, launch_game, run_autoplay  # noqa: E402
from games.minesweeper import board_config  # noqa: E402


async def main() -> None:
    enable_dpi_awareness()
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir, console=settings.log_console)

    config = MinesweeperConfig.from_board_config(
        board_config(),
        max_steps=300,
        tool_timeout=settings.tool_timeout,
    )
    proc = launch_game()
    try:
        time.sleep(1.5)  # 等游戏窗口出现
        llm = OpenAICompatProvider(settings)
        print(f"开始自动扫雷（模型={settings.model}，Ctrl+C 停止）...")
        result = await run_autoplay(config, llm)
        print("\n===== 结束 =====")
        print(result.output)
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
