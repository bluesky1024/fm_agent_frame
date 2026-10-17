"""基于官方 openai SDK 的 OpenAI 兼容协议实现（DeepSeek 等）。

内部消息模型是「扁平 / 已解析」的（ToolCall.arguments 是 dict），
而 OpenAI 线上协议是「嵌套 / 原始」的（arguments 是 JSON 字符串）。
本模块负责两者之间的双向转换，把协议细节隔离在 provider 内部。

整包与流式共用同一套消息转换；流式额外负责：
- 文本增量透传；
- 按 index 拼接分片的 tool_calls（id / name / arguments 都可能分片到达）；
- 从最终 chunk 提取用量。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)

from agent_frame.core.config import Settings, get_settings
from agent_frame.core.errors import LLMError
from agent_frame.core.images import save_images_and_strip
from agent_frame.core.messages import Message, ToolCall
from agent_frame.core.types import TokenUsage, ToolSpec
from agent_frame.llm.base import ChatResult, StreamChunk

logger = logging.getLogger("agent_frame.llm")


class OpenAICompatProvider:
    """把任意 OpenAI 兼容服务（DeepSeek）包装成 LLMProvider。"""

    def __init__(self, settings: Settings | None = None, *, client: Any | None = None) -> None:
        self._settings = settings or get_settings()
        if client is not None:
            self._client = client
            return
        if not self._settings.deepseek_api_key:
            raise LLMError("缺少 API key：请设置环境变量 DEEPSEEK_API_KEY，或在 .env 中填写")
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
        payload_tools = _tool_payload(tools)
        openai_messages = _to_openai_messages(messages)
        self._log_request(openai_messages, payload_tools)
        try:
            resp = await self._client.chat.completions.create(
                model=self._settings.model,
                messages=openai_messages,
                tools=payload_tools,
            )
        except Exception as exc:
            raise _map_error(exc) from exc

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
        logger.debug(
            "LLM 响应 | %s",
            json.dumps(resp.model_dump(mode="json"), ensure_ascii=False),
        )
        return ChatResult(
            content=choice.content,
            tool_calls=tool_calls,
            usage=_to_usage(getattr(resp, "usage", None)),
        )

    async def stream(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        payload_tools = _tool_payload(tools)
        openai_messages = _to_openai_messages(messages)
        self._log_request(openai_messages, payload_tools)

        content_parts: list[str] = []
        call_fragments: dict[int, dict[str, str]] = {}
        finish_reason: str | None = None
        usage = TokenUsage()

        try:
            response = await self._client.chat.completions.create(
                model=self._settings.model,
                messages=openai_messages,
                tools=payload_tools,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in response:
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    usage = _to_usage(chunk_usage)

                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                choice = choices[0]
                finish_reason = getattr(choice, "finish_reason", None) or finish_reason
                delta = choice.delta

                text = getattr(delta, "content", None)
                if text:
                    content_parts.append(text)
                    yield StreamChunk(text_delta=text)

                for fragment in getattr(delta, "tool_calls", None) or []:
                    _accumulate_fragment(call_fragments, fragment)
        except Exception as exc:
            raise _map_error(exc) from exc

        result = ChatResult(
            content="".join(content_parts) or None,
            tool_calls=_build_tool_calls(call_fragments),
            usage=usage,
            finish_reason=finish_reason,
        )
        logger.debug(
            "LLM 流式响应 | %s",
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False),
        )
        yield StreamChunk(result=result)

    def _log_request(
        self, openai_messages: list[dict[str, Any]], payload_tools: list[dict[str, Any]] | None
    ) -> None:
        pic_dir = Path(self._settings.log_dir) / "pic"
        logger.debug(
            "LLM 请求 | %s",
            json.dumps(
                {
                    "model": self._settings.model,
                    "messages": save_images_and_strip(openai_messages, pic_dir),
                    "tools": payload_tools,
                },
                ensure_ascii=False,
            ),
        )


def _tool_payload(tools: Sequence[ToolSpec] | None) -> list[dict[str, Any]] | None:
    """把工具描述转成 OpenAI function calling 的线上结构。"""
    return [{"type": "function", "function": t.model_dump()} for t in tools] if tools else None


def _to_openai_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
    """把内部 Message 转成 OpenAI 线上协议的 dict 列表。"""
    out: list[dict[str, Any]] = []
    for m in messages:
        d: dict[str, Any] = {"role": m.role}
        if m.content is not None:
            if isinstance(m.content, str):
                d["content"] = m.content
            else:
                d["content"] = [part.model_dump() for part in m.content]
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


def _accumulate_fragment(fragments: dict[int, dict[str, str]], raw: Any) -> None:
    """把流式 tool_call 分片按 index 累加。"""
    index = getattr(raw, "index", 0)
    entry = fragments.setdefault(index, {"id": "", "name": "", "arguments": ""})
    call_id = getattr(raw, "id", None)
    if call_id:
        entry["id"] = call_id
    function = getattr(raw, "function", None)
    if function is not None:
        name = getattr(function, "name", None)
        if name:
            entry["name"] = name
        arguments = getattr(function, "arguments", None)
        if arguments:
            entry["arguments"] += arguments


def _build_tool_calls(fragments: dict[int, dict[str, str]]) -> list[ToolCall] | None:
    """按 index 顺序把累加后的分片构造成 ToolCall 列表。"""
    if not fragments:
        return None
    return [
        ToolCall(
            id=fragments[index]["id"],
            name=fragments[index]["name"],
            arguments=_parse_arguments(fragments[index]["arguments"]),
        )
        for index in sorted(fragments)
    ]


def _to_usage(raw: Any) -> TokenUsage:
    """从 OpenAI 用量对象提取 TokenUsage；缺失时返回全零。"""
    if raw is None:
        return TokenUsage()
    return TokenUsage(
        prompt_tokens=getattr(raw, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(raw, "completion_tokens", 0) or 0,
        total_tokens=getattr(raw, "total_tokens", 0) or 0,
    )


def _map_error(exc: Exception) -> LLMError:
    """把供应商/网络异常映射为框架异常，并标注是否可重试。"""
    retryable = isinstance(
        exc,
        (
            TimeoutError,
            ConnectionError,
            asyncio.TimeoutError,
            APITimeoutError,
            APIConnectionError,
            RateLimitError,
            InternalServerError,
        ),
    )
    return LLMError(f"LLM 调用失败: {exc}", retryable=retryable)


def _parse_arguments(raw: str | None) -> dict[str, Any]:
    """把 OpenAI 返回的 JSON 字符串参数解析成 dict，解析失败则返回空 dict。"""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
