"""LLM 供应商协议：整包、流式、用量与错误映射（S2 接缝，伪 wire chunk）。"""

from types import SimpleNamespace

import pytest

from agent_frame.core.config import Settings
from agent_frame.core.errors import LLMError
from agent_frame.core.messages import Message, ToolCall
from agent_frame.llm import OpenAICompatProvider
from agent_frame.llm.openai_compat import _to_openai_messages


def _wire_usage(prompt: int = 0, completion: int = 0, total: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
    )


def _wire_chunk(
    *,
    content: str | None = None,
    tool_calls: list | None = None,
    finish_reason: str | None = None,
    usage: SimpleNamespace | None = None,
    no_choices: bool = False,
) -> SimpleNamespace:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choices = [] if no_choices else [SimpleNamespace(delta=delta, finish_reason=finish_reason)]
    return SimpleNamespace(choices=choices, usage=usage)


def _tool_delta(
    *, index: int = 0, call_id: str | None = None, name: str | None = None, arguments: str = ""
) -> SimpleNamespace:
    return SimpleNamespace(
        index=index,
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class _FakeStreamCompletions:
    def __init__(self, chunks: list[SimpleNamespace]) -> None:
        self._chunks = chunks
        self.kwargs: dict = {}

    async def create(self, **kwargs):
        self.kwargs = kwargs
        chunks = self._chunks

        async def iterator():
            for chunk in chunks:
                yield chunk

        return iterator()


class _FakeStreamClient:
    def __init__(self, chunks: list[SimpleNamespace]) -> None:
        self.completions = _FakeStreamCompletions(chunks)
        self.chat = SimpleNamespace(completions=self.completions)


def _provider(client) -> OpenAICompatProvider:
    return OpenAICompatProvider(Settings(deepseek_api_key="test-key"), client=client)


async def test_stream_yields_text_deltas_and_final_result() -> None:
    client = _FakeStreamClient(
        [
            _wire_chunk(content="你"),
            _wire_chunk(content="好"),
            _wire_chunk(content="", finish_reason="stop"),
            _wire_chunk(no_choices=True, usage=_wire_usage(3, 2, 5)),
        ]
    )
    provider = _provider(client)

    chunks = [c async for c in provider.stream([Message.user("hi")])]

    assert [c.text_delta for c in chunks if c.text_delta] == ["你", "好"]
    final = chunks[-1].result
    assert final is not None
    assert final.content == "你好"
    assert final.usage.total_tokens == 5
    assert final.usage.prompt_tokens == 3
    assert final.usage.completion_tokens == 2
    assert client.completions.kwargs["stream"] is True


async def test_stream_assembles_fragmented_tool_calls() -> None:
    client = _FakeStreamClient(
        [
            _wire_chunk(
                tool_calls=[_tool_delta(call_id="c1", name="calculator", arguments='{"expr')]
            ),
            _wire_chunk(tool_calls=[_tool_delta(arguments='ession": "1+1"}')]),
            _wire_chunk(finish_reason="tool_calls"),
        ]
    )
    provider = _provider(client)

    chunks = [c async for c in provider.stream([Message.user("算一下")])]
    final = chunks[-1].result

    assert final is not None
    assert final.tool_calls == [
        ToolCall(id="c1", name="calculator", arguments={"expression": "1+1"})
    ]
    assert final.has_tool_calls


async def test_stream_keeps_parallel_tool_call_fragments_separate() -> None:
    client = _FakeStreamClient(
        [
            _wire_chunk(
                tool_calls=[
                    _tool_delta(index=0, call_id="a", name="one", arguments='{"x": 1}'),
                    _tool_delta(index=1, call_id="b", name="two", arguments='{"y": 2}'),
                ]
            ),
            _wire_chunk(finish_reason="tool_calls"),
        ]
    )
    provider = _provider(client)

    chunks = [c async for c in provider.stream([Message.user("两个一起")])]
    final = chunks[-1].result

    assert final is not None
    assert [tc.id for tc in final.tool_calls] == ["a", "b"]
    assert [tc.arguments for tc in final.tool_calls] == [{"x": 1}, {"y": 2}]


class _FakeChatCompletions:
    def __init__(self, response: SimpleNamespace) -> None:
        self._response = response
        self.kwargs: dict = {}

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self._response


class _FakeChatClient:
    def __init__(self, response: SimpleNamespace) -> None:
        self.completions = _FakeChatCompletions(response)
        self.chat = SimpleNamespace(completions=self.completions)


def _wire_response(
    *,
    content: str | None = "你好",
    tool_calls: list | None = None,
    usage: SimpleNamespace | None = None,
) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=usage,
        model_dump=lambda mode="json": {"choices": [{"message": {"content": content}}]},
    )


async def test_chat_extracts_usage() -> None:
    client = _FakeChatClient(_wire_response(usage=_wire_usage(7, 4, 11)))
    provider = _provider(client)

    result = await provider.chat([Message.user("hi")])

    assert result.content == "你好"
    assert result.usage.prompt_tokens == 7
    assert result.usage.completion_tokens == 4
    assert result.usage.total_tokens == 11
    assert client.completions.kwargs.get("stream") is not True


async def test_chat_parses_tool_call_arguments() -> None:
    wire_calls = [
        SimpleNamespace(
            id="c9",
            function=SimpleNamespace(name="get_current_time", arguments="{}"),
        )
    ]
    client = _FakeChatClient(_wire_response(content=None, tool_calls=wire_calls))
    provider = _provider(client)

    result = await provider.chat([Message.user("几点了")])

    assert result.tool_calls is not None
    assert result.tool_calls[0] == ToolCall(id="c9", name="get_current_time", arguments={})


async def test_provider_maps_failures_to_llm_error() -> None:
    class ExplodingCompletions:
        async def create(self, **kwargs):
            raise TimeoutError("timeout")

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=ExplodingCompletions()),
    )
    provider = _provider(client)

    with pytest.raises(LLMError) as excinfo:
        await provider.chat([Message.user("hi")])

    assert excinfo.value.retryable is True


def test_message_conversion_happens_before_wire_call() -> None:
    converted = _to_openai_messages([Message.user("hi")])
    assert converted == [{"role": "user", "content": "hi"}]
