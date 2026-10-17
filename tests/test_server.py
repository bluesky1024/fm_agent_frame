"""票 09：服务层多会话、非法输入与 HTTP/SSE 冒烟。"""

import json
from typing import Any

from fastapi.testclient import TestClient

from agent_frame.core.messages import Message
from agent_frame.interfaces.server import (
    AgentService,
    ChatRequest,
    InvalidRequestError,
    create_app,
)
from agent_frame.interfaces.session import InMemorySession, SessionManager
from agent_frame.llm.base import ChatResult, StreamChunk
from agent_frame.runtime import AgentRuntime, AgentSpec


class ScriptedLLM:
    def __init__(self, results: list[ChatResult]) -> None:
        self._results = list(results)
        self.requests: list[list[Message]] = []

    async def chat(self, messages, tools=None, *, model=None) -> ChatResult:
        raise AssertionError("runtime 应使用 stream()")

    async def stream(self, messages, tools=None, *, model=None):
        self.requests.append(list(messages))
        yield StreamChunk(result=self._results.pop(0))


def _spec(llm: Any) -> AgentSpec:
    return AgentSpec(llm=llm, name="server-agent", system_prompt="你是助手", max_steps=2)


def _service(llm: Any) -> AgentService:
    return AgentService(AgentRuntime(), _spec(llm), SessionManager())


def test_session_manager_create_get_delete() -> None:
    manager = SessionManager()
    session = manager.create("s1")

    assert session.id == "s1"
    assert manager.get("s1") is session
    assert manager.get_or_create("s1") is session
    assert manager.ids() == ["s1"]

    manager.delete("s1")
    assert manager.get("s1") is None
    assert manager.ids() == []


async def test_service_sessions_are_isolated() -> None:
    llm = ScriptedLLM([ChatResult(content="答一"), ChatResult(content="答二")])
    service = _service(llm)

    first = await service.chat(ChatRequest(message="会话一", session_id="s1"))
    second = await service.chat(ChatRequest(message="会话二", session_id="s2"))

    assert first.session_id == "s1"
    assert second.session_id == "s2"
    second_request = [str(m.content) for m in llm.requests[1]]
    assert "会话二" in second_request
    assert "会话一" not in second_request


async def test_service_stream_yields_runtime_events() -> None:
    llm = ScriptedLLM([ChatResult(content="你好")])
    service = _service(llm)

    events = [event async for event in service.stream(ChatRequest(message="hi", session_id="s1"))]

    assert events[0].type == "run_start"
    assert events[-1].type == "run_end"


async def test_service_rejects_blank_message() -> None:
    service = _service(ScriptedLLM([]))
    request = ChatRequest.model_construct(message="   ", session_id="s1", stream=True)

    try:
        await service.chat(request)
    except InvalidRequestError as exc:
        assert "不能为空" in str(exc)
    else:
        raise AssertionError("空白输入应被拒绝")


def test_http_chat_streams_sse_events() -> None:
    client = TestClient(create_app(_service(ScriptedLLM([ChatResult(content="你好")]))))

    response = client.post("/chat", json={"message": "hi", "session_id": "s1"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    lines = response.text.splitlines()
    payloads = [line[len("data: ") :] for line in lines if line.startswith("data: ")]
    events = [json.loads(payload) for payload in payloads]
    assert events[0]["type"] == "run_start"
    assert events[-1]["type"] == "run_end"
    assert events[-1]["result"]["output"] == "你好"


def test_http_invalid_input_returns_structured_error() -> None:
    client = TestClient(create_app(_service(ScriptedLLM([]))))

    response = client.post("/chat", json={"message": "   "})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["type"] == "validation_error"
    assert "不能为空" in body["error"]["message"]


def test_http_non_stream_response() -> None:
    client = TestClient(create_app(_service(ScriptedLLM([ChatResult(content="答复")]))))

    response = client.post("/chat", json={"message": "hi", "session_id": "s1", "stream": False})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "答复"
    assert body["session_id"] == "s1"
    assert body["usage"] is not None


def test_service_exposes_session_after_chat() -> None:
    service = _service(ScriptedLLM([ChatResult(content="ok")]))
    session = service.sessions.get_or_create("s1")
    session.state["k"] = "v"

    assert isinstance(session, InMemorySession)
    assert service.get_session("s1") is session
    assert session.state == {"k": "v"}
