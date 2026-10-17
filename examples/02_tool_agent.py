"""示例 2：工具 Agent —— 运行时循环 + 工具调用。

让 Agent 自主决定调用 calculator / get_current_time 工具来回答问题。
事件流会展示工具请求、工具结果与下一轮推理。

运行：python examples/02_tool_agent.py
调试：LOG_LEVEL=DEBUG python examples/02_tool_agent.py
前提：已设置 DEEPSEEK_API_KEY（环境变量或 .env 文件）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from _events import run_and_print

from agent_frame.core.config import get_settings
from agent_frame.interfaces.session import InMemorySession
from agent_frame.llm import OpenAICompatProvider
from agent_frame.obs import JSONLTracer, setup_logging
from agent_frame.runtime import AgentRuntime, AgentSpec
from agent_frame.tools.builtin import CalculatorTool, CurrentTimeTool


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir, console=settings.log_console)

    provider = OpenAICompatProvider(settings)
    spec = AgentSpec(
        llm=provider,
        name="tool-agent",
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
        tracers=[JSONLTracer(Path(settings.log_dir) / "trace.jsonl")],
    )
    runtime = AgentRuntime()
    session = InMemorySession(id="tool-agent")

    task = (
        input("请输入你的问题（如：现在几点？3 的 4 次方加 10 是多少？）：")
        or "3 的 4 次方加 10 是多少？"
    )
    await run_and_print(runtime, spec, session, task)


if __name__ == "__main__":
    asyncio.run(main())
