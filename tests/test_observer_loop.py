from agent_frame.agent import ToolUseAgent
from agent_frame.llm.base import ChatResult
from agent_frame.messages import Message, ToolCall
from agent_frame.tools import ToolRegistry
from agent_frame.tools.builtin import CalculatorTool


class RecordingObserver:
    def __init__(self) -> None:
        self.count = 0

    async def observe(self) -> Message:
        self.count += 1
        return Message.user(f"frame-{self.count}")


class OneToolThenTextLLM:
    def __init__(self) -> None:
        self.calls = []

    async def chat(self, messages, tools=None):
        self.calls.append(list(messages))
        if len(self.calls) == 1:
            return ChatResult(
                tool_calls=[
                    ToolCall(id="1", name="calculator", arguments={"expression": "2+2"})
                ]
            )
        return ChatResult(content="done")


async def test_observer_injects_frame_before_first_and_after_tool_batch():
    llm = OneToolThenTextLLM()
    obs = RecordingObserver()
    agent = ToolUseAgent(llm, ToolRegistry([CalculatorTool()]), observer=obs)

    await agent.run("play")

    # 首帧 + 一批工具执行后一帧
    assert obs.count == 2
    # 第一轮 chat 收到首帧
    assert llm.calls[0][-1].content == "frame-1"
    # 第二轮 chat 同时含有两帧
    second_contents = [m.content for m in llm.calls[1]]
    assert "frame-1" in second_contents
    assert "frame-2" in second_contents


async def test_no_observer_keeps_default_behavior():
    llm = OneToolThenTextLLM()
    agent = ToolUseAgent(llm, ToolRegistry([CalculatorTool()]))

    result = await agent.run("hi")

    assert result.output == "done"
    assert len(result.steps) == 2
