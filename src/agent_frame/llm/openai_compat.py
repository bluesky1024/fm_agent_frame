"""基于官方 openai SDK 的 OpenAI 兼容协议实现（DeepSeek 等）。

内部消息模型是「扁平 / 已解析」的（ToolCall.arguments 是 dict），
而 OpenAI 线上协议是「嵌套 / 原始」的（arguments 是 JSON 字符串）。
本模块负责两者之间的双向转换，把协议细节隔离在 provider 内部。
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from openai import AsyncOpenAI

from agent_frame.config import Settings, get_settings
from agent_frame.errors import LLMError
from agent_frame.llm.base import ChatResult, LLMProvider, ToolSpec
from agent_frame.messages import Message, ToolCall


class OpenAICompatProvider:
    """把任意 OpenAI 兼容服务（DeepSeek）包装成 LLMProvider。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.deepseek_api_key:
            raise LLMError(
                "缺少 API key：请设置环境变量 DEEPSEEK_API_KEY，或在 .env 中填写"
            )
        self._client = AsyncOpenAI(
            api_key=self._settings.deepseek_api_key,
            base_url=self._settings.deepseek_base_url,
            timeout=self._settings.request_timeout,
            max_retries=self._settings.max_retries,
        )

    async def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ChatResult:
        payload_tools = (
            [{"type": "function", "function": t.model_dump()} for t in tools]
            if tools
            else None
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._settings.model,
                messages=_to_openai_messages(messages),
                tools=payload_tools,
            )
        except Exception as exc:  # noqa: BLE001 - 统一转成框架异常
            raise LLMError(f"LLM 调用失败: {exc}") from exc

        choice = resp.choices[0].message
        tool_calls = None
        if choice.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id or "",
                    name=tc.function.name,
                    arguments=_parse_arguments(tc.function.arguments),
                )
                for tc in choice.tool_calls
            ]
        return ChatResult(content=choice.content, tool_calls=tool_calls)


def _to_openai_messages(messages: Sequence[Message]) -> list[dict]:
    """把内部 Message 转成 OpenAI 线上协议的 dict 列表。"""
    out: list[dict] = []
    for m in messages:
        d: dict = {"role": m.role}
        if m.content is not None:
            d["content"] = m.content
        if m.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in m.tool_calls
            ]
        if m.tool_call_id is not None:
            d["tool_call_id"] = m.tool_call_id
        if m.name is not None:
            d["name"] = m.name
        out.append(d)
    return out


def _parse_arguments(raw: str | None) -> dict:
    """把 OpenAI 返回的 JSON 字符串参数解析成 dict，解析失败则返回空 dict。"""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
