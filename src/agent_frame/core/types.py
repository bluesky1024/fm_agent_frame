"""核心共享类型：工具描述、token 用量与运行结果。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    """给 LLM 描述一个可用工具（对应 OpenAI function 内层对象）。

    这是 LLM 层与工具层共同消费的共享类型，放在 core 以避免两层互相依赖。
    """

    name: str
    description: str
    parameters: dict[str, Any]


class TokenUsage(BaseModel):
    """一次或多次 LLM 调用的 token 用量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "TokenUsage") -> "TokenUsage":
        """返回两份用量的累加结果（不修改自身）。"""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return self.add(other)


class AgentResult(BaseModel):
    """一次运行的最终结果：最终文本、累计用量与步数。"""

    output: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    steps: int = 0
