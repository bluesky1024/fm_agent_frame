from agent_frame.agent import ToolUseAgent
from agent_frame.llm.base import ChatResult
from agent_frame.memory import ConversationMemory
from agent_frame.messages import ToolCall
from agent_frame.tools import ToolRegistry
from agent_frame.tools.builtin import CalculatorTool


class FakeLLM:
    """模拟 LLM：第一轮返回 tool_call，第二轮返回最终文本。"""

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return ChatResult(
                tool_calls=[ToolCall(id="1", name="calculator", arguments={"expression": "2+2"})]
            )
        return ChatResult(content="答案是 4")


async def test_tool_use_agent_loop():
    llm = FakeLLM()
    registry = ToolRegistry([CalculatorTool()])
    agent = ToolUseAgent(llm, registry)

    result = await agent.run("2 加 2 是多少？")

    assert result.output == "答案是 4"
    assert len(result.steps) == 2
    assert result.steps[0].tool_calls == ["calculator"]
    assert llm.calls == 2


class RecordingLLM:
    """记录每次调用收到的消息，返回固定文本。"""

    def __init__(self) -> None:
        self.calls = []

    async def chat(self, messages, tools=None):
        self.calls.append(list(messages))
        return ChatResult(content="ok")


async def test_agent_multiturn_accumulates_history():
    llm = RecordingLLM()
    registry = ToolRegistry([CalculatorTool()])
    memory = ConversationMemory()
    agent = ToolUseAgent(llm, registry)

    await agent.run("第一句", memory=memory, session_id="s1")
    await agent.run("第二句", memory=memory, session_id="s1")

    assert len(llm.calls) == 2
    first_messages, second_messages = llm.calls[0], llm.calls[1]
    # 第二轮应带上第一轮的历史，消息更多
    assert len(second_messages) > len(first_messages)
    assert second_messages[-1].role == "user"
    assert second_messages[-1].content == "第二句"


async def test_agent_sessions_are_isolated():
    llm = RecordingLLM()
    registry = ToolRegistry([CalculatorTool()])
    memory = ConversationMemory()
    agent = ToolUseAgent(llm, registry)

    await agent.run("s1 的第一句", memory=memory, session_id="s1")
    await agent.run("s2 的第一句", memory=memory, session_id="s2")

    second_contents = [m.content for m in llm.calls[1]]
    assert "s2 的第一句" in second_contents
    assert "s1 的第一句" not in second_contents
