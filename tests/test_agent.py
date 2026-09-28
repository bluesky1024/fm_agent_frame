from agent_frame.agent import ToolUseAgent
from agent_frame.llm.base import ChatResult
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
                tool_calls=[
                    ToolCall(id="1", name="calculator", arguments={"expression": "2+2"})
                ]
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
