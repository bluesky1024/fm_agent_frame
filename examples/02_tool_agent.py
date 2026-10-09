"""示例 2：首个完整演示 —— Agent 循环 + 工具调用。

让 Agent 自主决定调用 calculator / get_current_time 工具来回答问题。

运行：python examples/02_tool_agent.py
调试：LOG_LEVEL=DEBUG python examples/02_tool_agent.py
前提：已设置 DEEPSEEK_API_KEY（环境变量或 .env 文件）。
"""

from __future__ import annotations

import asyncio

from agent_frame.agent import ToolUseAgent
from agent_frame.config import get_settings
from agent_frame.llm import OpenAICompatProvider
from agent_frame.obs import setup_logging
from agent_frame.tools import ToolRegistry
from agent_frame.tools.builtin import CalculatorTool, CurrentTimeTool


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir, console=settings.log_console)
    llm = OpenAICompatProvider(settings)
    registry = ToolRegistry([CalculatorTool(), CurrentTimeTool()])
    agent = ToolUseAgent(
        llm,
        registry,
        system_prompt=(
            "你是一个会用工具的中文助手。"
            "需要计算时用 calculator，需要当前时间时用 get_current_time。"
        ),
        max_steps=settings.max_steps,
    )

    task = (
        input("请输入你的问题（如：现在几点？3 的 4 次方加 10 是多少？）：")
        or "3 的 4 次方加 10 是多少？"
    )
    result = await agent.run(task)

    print("\n===== 执行步骤 =====")
    for step in result.steps:
        print(f"[步骤 {step.index}] 工具: {step.tool_calls or '无'}")
    print("\n===== 最终回答 =====")
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
