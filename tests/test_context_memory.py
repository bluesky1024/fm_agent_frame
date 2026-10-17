"""票 06：上下文装配、摘要滑窗、多轮会话隔离与检索注入。"""

from typing import Any

from agent_frame.capabilities.retrieval import (
    DeterministicEmbedder,
    Document,
    InMemoryVectorStore,
    RetrievalContextProvider,
    SimpleRetriever,
)
from agent_frame.context import ContextBuilder
from agent_frame.core.messages import Message
from agent_frame.core.types import AgentResult
from agent_frame.interfaces.session import InMemorySession
from agent_frame.llm.base import ChatResult, StreamChunk
from agent_frame.memory import ConversationMemory, SummaryBufferMemory
from agent_frame.runtime import AgentRuntime, AgentSpec


class StaticProvider:
    def __init__(self, message: Message, placement: str | None = None) -> None:
        self._message = message
        if placement is not None:
            self.placement = placement

    async def provide(self, request) -> list[Message]:
        return [self._message]


async def test_context_builder_orders_system_providers_and_history() -> None:
    builder = ContextBuilder(
        [
            StaticProvider(Message.system("记忆召回：用户偏好中文")),
            StaticProvider(Message.system("检索片段：扫雷数字表示周围雷数")),
        ]
    )

    built = await builder.build(
        system_prompt="你是助手",
        history=[Message.user("历史问题")],
        user_input="当前问题",
        session_id="s1",
    )

    contents = [m.content for m in built.messages]
    assert contents == [
        "你是助手",
        "记忆召回：用户偏好中文",
        "检索片段：扫雷数字表示周围雷数",
        "历史问题",
    ]


async def test_context_builder_places_after_history_provider_last() -> None:
    builder = ContextBuilder(
        [
            StaticProvider(Message.system("记忆召回：用户偏好中文")),
            StaticProvider(Message.user("本轮最新截图"), placement="after_history"),
        ]
    )

    built = await builder.build(
        system_prompt="你是助手",
        history=[Message.user("历史问题"), Message.assistant("历史回答")],
        user_input="当前问题",
        session_id="s1",
    )

    contents = [m.content for m in built.messages]
    assert contents == [
        "你是助手",
        "记忆召回：用户偏好中文",
        "历史问题",
        "历史回答",
        "本轮最新截图",
    ]


async def test_summary_compaction_keeps_recent_window_and_raw_history() -> None:
    memory = SummaryBufferMemory()
    history = []
    for index in range(4):
        history.append(Message.user(f"第 {index} 个很长的问题" + "x" * 50))
        history.append(Message.assistant(f"第 {index} 个很长的回答" + "y" * 50))
    await memory.save("s1", history)

    compacted = await memory.compact("s1", token_threshold=1, keep_last=2)

    assert compacted is True
    view = await memory.view("s1")
    assert view[0].role == "system"
    assert str(view[0].content).startswith("此前对话摘要：")
    assert view[-2:] == history[-2:]
    # 原始历史不被改写
    assert await memory.load("s1") == history
    # 已抽干到只剩窗口，不再重复压缩
    assert await memory.compact("s1", token_threshold=1, keep_last=2) is False


class ScriptedLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.requests: list[list[Message]] = []

    async def chat(self, messages, tools=None, *, model=None) -> ChatResult:
        raise AssertionError("runtime 应使用 stream()")

    async def stream(self, messages, tools=None, *, model=None):
        self.requests.append(list(messages))
        content = self._responses.pop(0)
        yield StreamChunk(result=ChatResult(content=content))


def _spec(llm: Any, **overrides: Any) -> AgentSpec:
    values: dict[str, Any] = {
        "llm": llm,
        "name": "test",
        "system_prompt": "你是助手",
        "max_steps": 2,
    }
    values.update(overrides)
    return AgentSpec(**values)


async def test_runtime_applies_compacted_view_on_next_request() -> None:
    llm = ScriptedLLM(["答"])
    memory = SummaryBufferMemory()
    history = []
    for index in range(4):
        history.append(Message.user(f"旧问题 {index} " + "x" * 60))
        history.append(Message.assistant(f"旧回答 {index} " + "y" * 60))
    await memory.save("s1", history)

    session = InMemorySession(id="s1", memory=memory)
    spec = _spec(llm, context_token_budget=1, compaction_keep_last=2)

    await AgentRuntime().run_collect(spec, session, "新问题")

    request = llm.requests[0]
    assert request[0].content == "你是助手"
    assert request[1].role == "system"
    assert str(request[1].content).startswith("此前对话摘要：")
    assert request[-1].content == "新问题"
    # 最旧的完整消息不再逐条出现（内容可能被折进摘要）
    assert all(m.content != history[0].content for m in request)
    assert len(request) < len(history) + 2
    # 原始历史保留全部消息，且摘要没有写进历史
    persisted = await memory.load("s1")
    assert len(persisted) == len(history) + 2  # 新问题 + 回答
    assert all(not str(m.content).startswith("此前对话摘要") for m in persisted)


async def test_spec_memory_overrides_session_memory() -> None:
    memory = ConversationMemory()
    llm = ScriptedLLM(["答"])
    session = InMemorySession(id="s1")
    spec = _spec(llm, memory=memory)

    await AgentRuntime().run_collect(spec, session, "你好")

    stored = await memory.load("s1")
    assert [m.role for m in stored] == ["user", "assistant"]


async def test_sessions_are_isolated_and_accumulate_history() -> None:
    llm = ScriptedLLM(["答一", "答二", "答三"])
    memory = ConversationMemory()
    s1 = InMemorySession(id="s1", memory=memory)
    s2 = InMemorySession(id="s2", memory=memory)
    runtime = AgentRuntime()
    spec = _spec(llm)

    await runtime.run_collect(spec, s1, "会话一的问题")
    await runtime.run_collect(spec, s2, "会话二的问题")
    await runtime.run_collect(spec, s1, "会话一继续")

    s2_request = [str(m.content) for m in llm.requests[1]]
    assert "会话二的问题" in s2_request
    assert "会话一的问题" not in s2_request

    s1_second = [str(m.content) for m in llm.requests[2]]
    assert "会话一的问题" in s1_second
    assert "会话一继续" in s1_second
    assert "会话二的问题" not in s1_second

    assert s1.last_run is not None and s2.last_run is not None
    assert s1.last_run is not s2.last_run


async def _minesweeper_retriever() -> SimpleRetriever:
    retriever = SimpleRetriever(DeterministicEmbedder(), InMemoryVectorStore())
    await retriever.add_documents(
        [
            Document(content="扫雷规则：数字表示该格周围 8 格的雷数。"),
            Document(content="今天的天气晴朗，适合出门散步。"),
        ]
    )
    return retriever


async def test_retrieval_provider_injects_snippet_without_persisting_it() -> None:
    retriever = await _minesweeper_retriever()
    provider = RetrievalContextProvider(retriever, top_k=1)
    llm = ScriptedLLM(["按规则判断"])
    session = InMemorySession(id="s1")
    spec = _spec(llm, context_providers=[provider])

    await AgentRuntime().run_collect(spec, session, "扫雷时数字代表什么？")

    request = llm.requests[0]
    injected = [m for m in request if m.role == "system" and "相关背景资料" in str(m.content)]
    assert len(injected) == 1
    assert "扫雷" in str(injected[0].content)
    assert "天气" not in str(injected[0].content)
    assert all("相关背景资料" not in str(m.content) for m in session.history)


async def test_retrieval_is_deterministic() -> None:
    retriever = await _minesweeper_retriever()

    first = await retriever.retrieve("扫雷数字", top_k=1)
    second = await retriever.retrieve("扫雷数字", top_k=1)

    assert first[0].chunk.chunk_id == second[0].chunk.chunk_id
    assert first[0].score == second[0].score


def test_agent_result_type_is_used_by_session() -> None:
    session = InMemorySession(id="s1")
    session.last_run = AgentResult(output="完成", steps=1)
    assert session.last_run.output == "完成"
