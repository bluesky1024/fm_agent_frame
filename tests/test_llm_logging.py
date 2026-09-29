import logging

from agent_frame.config import Settings
from agent_frame.llm import OpenAICompatProvider
from agent_frame.messages import Message


class _FakeMessage:
    content = "你好"
    tool_calls = None


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]


class _FakeCompletions:
    async def create(self, **kwargs):
        return _FakeResponse()


class _FakeChat:
    completions = _FakeCompletions()


class _FakeClient:
    chat = _FakeChat()


async def test_provider_emits_debug_logs(caplog):
    caplog.set_level(logging.DEBUG)

    settings = Settings(deepseek_api_key="test-key")
    provider = OpenAICompatProvider(settings)
    provider._client = _FakeClient()  # 替换真实 client，避免联网

    result = await provider.chat([Message.user("你好")])

    assert result.content == "你好"
    messages = [r.message for r in caplog.records]
    assert any("LLM 请求" in m for m in messages)
    assert any("LLM 响应" in m for m in messages)
