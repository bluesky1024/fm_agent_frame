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


async def test_only_latest_frame_is_sent_to_llm():
    llm = OneToolThenTextLLM()
    obs = RecordingObserver()
    agent = ToolUseAgent(llm, ToolRegistry([CalculatorTool()]), observer=obs)

    await agent.run("play")

    # 两个注入点各观察一次（首帧前 + 一批工具执行后）
    assert obs.count == 2
    # 第一次请求：历史末尾是首帧
    assert llm.calls[0][-1].content == "frame-1"
    # 第二次请求：末尾是最新帧；旧帧不再出现
    second = [m.content for m in llm.calls[1]]
    assert second[-1] == "frame-2"
    assert "frame-1" not in second


async def test_growth_history_keeps_text_but_no_old_frames():
    llm = OneToolThenTextLLM()
    obs = RecordingObserver()
    agent = ToolUseAgent(llm, ToolRegistry([CalculatorTool()]), observer=obs)

    await agent.run("play")

    # 文本进展（assistant 工具调用 + 工具结果）保留在历史里
    second_roles = [m.role for m in llm.calls[1]]
    assert "tool" in second_roles
    # 历史里最多只有一帧（当前帧），不随轮数累积
    frame_count = sum(1 for m in llm.calls[1] if str(m.content).startswith("frame-"))
    assert frame_count == 1


async def test_no_observer_keeps_default_behavior():
    llm = OneToolThenTextLLM()
    agent = ToolUseAgent(llm, ToolRegistry([CalculatorTool()]))

    result = await agent.run("hi")

    assert result.output == "done"
    assert len(result.steps) == 2
