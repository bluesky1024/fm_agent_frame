"""示例 1：最简 Agent —— 用 AgentSpec 声明一个纯对话 agent。

运行：python examples/01_hello_llm.py
调试：LOG_LEVEL=DEBUG python examples/01_hello_llm.py
前提：已设置 DEEPSEEK_API_KEY（环境变量或 .env 文件）。

你会看到完整事件流：运行开始 → 步骤 → 上下文装配 → 文本增量 → 运行结束。
"""

from __future__ import annotations

import asyncio

from _events import run_and_print

from agent_frame.core.config import get_settings
from agent_frame.interfaces.session import InMemorySession
from agent_frame.llm import OpenAICompatProvider
from agent_frame.obs import setup_logging
from agent_frame.runtime import AgentRuntime, AgentSpec


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir, console=settings.log_console)

    provider = OpenAICompatProvider(settings)
    spec = AgentSpec(
        llm=provider,
        name="hello",
        model=settings.model,
        system_prompt="你是一个简洁的中文助手。",
        max_steps=1,
    )
    runtime = AgentRuntime()
    session = InMemorySession(id="hello")

    await run_and_print(runtime, spec, session, "用一句话解释什么是 Agent？")


if __name__ == "__main__":
    asyncio.run(main())
