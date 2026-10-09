"""示例 3：交互式多轮对话 —— 持续交互，而非一次任务跑完退出。

每轮你输入一句话，Agent 处理（内部仍会自主调工具）并回复；
ConversationMemory 保存历史，所以它能记住前面聊过的内容。

运行：python examples/03_interactive.py
退出：输入 exit / quit，或 Ctrl+D
前提：已设置 DEEPSEEK_API_KEY（环境变量或 .env 文件）。
"""

from __future__ import annotations

import asyncio

from agent_frame.agent import ToolUseAgent
from agent_frame.config import get_settings
from agent_frame.llm import OpenAICompatProvider
from agent_frame.memory import ConversationMemory
from agent_frame.obs import setup_logging
from agent_frame.tools import ToolRegistry
from agent_frame.tools.builtin import CalculatorTool, CurrentTimeTool


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir)

    llm = OpenAICompatProvider(settings)
    registry = ToolRegistry([CalculatorTool(), CurrentTimeTool()])
    memory = ConversationMemory()
    agent = ToolUseAgent(
        llm,
        registry,
        system_prompt=(
            "你是一个会用工具的中文助手。"
            "需要计算时用 calculator，需要当前时间时用 get_current_time。"
        ),
        max_steps=settings.max_steps,
    )

    print("进入交互模式（输入 exit / quit 退出）。")
    while True:
        try:
            user_input = input("\n你> ")
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input.strip():
            continue
        if user_input.strip().lower() in ("exit", "quit"):
            print("再见！")
            break

        result = await agent.run(user_input, memory=memory, session_id="interactive")
        print(f"Agent> {result.output}")


if __name__ == "__main__":
    asyncio.run(main())
