"""示例 4：扫雷视觉 Agent（多模态计算机使用）。

让 Agent 反复：截取扫雷棋盘截图 → 看图决策 → 控制鼠标点击/插旗 → 再看，
直到赢下或踩雷后自动重开，持续对局。

运行：
    MODEL=deepseek-flash python examples/04_minesweeper_agent.py
前提：
    - 已设置 DEEPSEEK_API_KEY（环境变量或 .env）。
    - 已校准 config/minesweeper.json 的几何/区域/重开参数。
    - 目标扫雷窗口保持在校准时的位置与大小（本期假设窗口固定不移动）。
停止：Ctrl+C。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from agent_frame.config import get_settings
from agent_frame.desktop.minesweeper import build_agent, load_config
from agent_frame.desktop.mouse import enable_dpi_awareness
from agent_frame.llm import OpenAICompatProvider
from agent_frame.obs import setup_logging

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "minesweeper.json"


async def main() -> None:
    enable_dpi_awareness()
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir, console=settings.log_console)

    config = load_config(CONFIG_PATH)
    llm = OpenAICompatProvider(settings)
    agent = build_agent(config, llm)

    print(f"开始自动扫雷（模型={settings.model}，Ctrl+C 停止）...")
    result = await agent.run("赢下这局扫雷。")
    print("\n===== 结束 =====")
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
