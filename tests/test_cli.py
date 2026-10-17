"""最小 CLI：可注入输入/输出，退出指令生效。"""

from agent_frame.interfaces import ChatCLI, InMemorySession
from agent_frame.llm.base import ChatResult, StreamChunk
from agent_frame.runtime import AgentRuntime, AgentSpec


class ScriptedLLM:
    def __init__(self, results: list[str]) -> None:
        self._results = list(results)

    async def chat(self, messages, tools=None) -> ChatResult:
        raise AssertionError("runtime 应使用 stream()")

    async def stream(self, messages, tools=None):
        yield StreamChunk(result=ChatResult(content=self._results.pop(0)))


async def test_cli_runs_multiple_turns_and_exits() -> None:
    inputs = iter(["第一句", "第二句", "exit"])
    outputs: list[str] = []
    cli = ChatCLI(
        AgentRuntime(),
        AgentSpec(llm=ScriptedLLM(["答一", "答二"]), name="cli", max_steps=1),
        InMemorySession(id="cli"),
        input_fn=lambda prompt: next(inputs),
        output_fn=outputs.append,
    )

    await cli.run()

    assert "Agent> 答一" in outputs
    assert "Agent> 答二" in outputs
    assert outputs[-1] == "再见！"
