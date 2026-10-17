"""示例 3：交互式多轮对话 —— 同一个 Session 跨多轮保存历史。

每轮输入一句话，Agent 处理（内部仍会自主调工具）并回复；
Session 保存历史，所以它能记住前面聊过的内容。

运行：python examples/03_interactive.py
退出：输入 exit / quit，或 Ctrl+D
前提：已设置 DEEPSEEK_API_KEY（环境变量或 .env 文件）。
"""

from __future__ import annotations

import asyncio

from _events import run_and_print

from agent_frame.core.config import get_settings
from agent_frame.interfaces.session import InMemorySession
from agent_frame.llm import OpenAICompatProvider
from agent_frame.obs import setup_logging
from agent_frame.runtime import AgentRuntime, AgentSpec
from agent_frame.tools.builtin import CalculatorTool, CurrentTimeTool


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir, console=settings.log_console)

    provider = OpenAICompatProvider(settings)
    spec = AgentSpec(
        llm=provider,
        name="interactive",
        model=settings.model,
        system_prompt=(
            "你是一个会用工具的中文助手。"
            "需要计算时用 calculator，需要当前时间时用 get_current_time。"
        ),
        tools=[CalculatorTool(), CurrentTimeTool()],
        max_steps=settings.max_steps,
        tool_timeout=settings.tool_timeout,
        context_token_budget=settings.context_token_budget,
        compaction_keep_last=settings.compaction_keep_last,
    )
    runtime = AgentRuntime()
    session = InMemorySession(id="interactive")

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

        print("\nAgent> ", end="", flush=True)
        await run_and_print(runtime, spec, session, user_input)
        print()


if __name__ == "__main__":
    asyncio.run(main())
