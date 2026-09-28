"""示例 1：最简单的单轮问答 —— 发消息给 DeepSeek，拿回文本回复。

运行：python examples/01_hello_llm.py
前提：已设置 DEEPSEEK_API_KEY（环境变量或 .env 文件）。
"""

from __future__ import annotations

import asyncio

from agent_frame.llm import OpenAICompatProvider
from agent_frame.messages import Message


async def main() -> None:
    provider = OpenAICompatProvider()
    reply = await provider.chat(
        [Message.system("你是一个简洁的中文助手。"), Message.user("用一句话解释什么是 Agent？")]
    )
    print("回复：", reply.content)


if __name__ == "__main__":
    asyncio.run(main())
