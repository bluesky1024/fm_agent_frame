"""ToolUseAgent：ReAct 风格的「思考 → 调工具 → 观察 → 再思考」循环。

这是整个框架的核心机制：LLM 不直接给出最终答案，
而是先决定「要不要调用工具」，循环直到它给出纯文本回答为止。

可选装配 observer（观察者）：在首轮之前、以及每批工具执行之后，
各取一帧最新观察（通常是带图的 user 消息），支持「看 → 做 → 再看」的多模态场景。

观察帧**不进永久对话历史**，而是作为「当前帧」随每次请求临时附加：
发给 LLM 的永远是「完整文本历史 + 一帧最新截图」。这样历史里的旧截图不会
被反复重发，请求体不随轮数膨胀。
"""

from __future__ import annotations

from agent_frame.agent.base import AgentResult, AgentStep, Observer
from agent_frame.core.errors import AgentLoopError
from agent_frame.core.messages import Message
from agent_frame.llm.base import LLMProvider
from agent_frame.memory.base import Memory
from agent_frame.tools.registry import ToolRegistry


class ToolUseAgent:
    """一个会用工具的 Agent。"""

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        *,
        system_prompt: str | None = None,
        max_steps: int = 8,
        observer: Observer | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._system_prompt = system_prompt
        self._max_steps = max_steps
        self._observer = observer

    async def run(
        self,
        task: str,
        *,
        memory: Memory | None = None,
        session_id: str = "default",
    ) -> AgentResult:
        """处理一次用户输入（单轮）。

        传入同一个 memory + session_id 即可实现多轮对话：每次都会先
        load 该会话的历史，跑完再 save 回去。
        """
        messages: list[Message] = []
        if self._system_prompt:
            messages.append(Message.system(self._system_prompt))
        if memory is not None:
            messages.extend(await memory.load(session_id))
        messages.append(Message.user(task))

        # 观察帧不进历史：作为「当前帧」随每次请求临时附加
        frame = await self._observer.observe() if self._observer is not None else None

        tool_specs = self._tools.to_tool_specs()
        steps: list[AgentStep] = []

        for index in range(self._max_steps):
            payload = messages + ([frame] if frame is not None else [])
            result = await self._llm.chat(payload, tool_specs)

            # LLM 决定调用工具：逐个执行，把结果作为 tool 消息回填，进入下一轮
            if result.has_tool_calls and result.tool_calls:
                messages.append(Message.assistant(tool_calls=result.tool_calls))
                called: list[str] = []
                for tc in result.tool_calls:
                    try:
                        output = await self._tools.call(tc.name, tc.arguments)
                    except Exception as exc:  # noqa: BLE001 - 工具异常回填给 LLM 让其修正
                        output = f"工具执行出错: {exc}"
                    messages.append(Message.tool(tool_call_id=tc.id, content=output, name=tc.name))
                    called.append(tc.name)
                steps.append(AgentStep(index=index, tool_calls=called))
                if self._observer is not None:
                    frame = await self._observer.observe()  # 替换当前帧，不 append 进历史
                continue

            # LLM 给出最终文本回答
            final = result.content or ""
            messages.append(Message.assistant(content=final))
            steps.append(AgentStep(index=index, content=final))
            if memory is not None:
                await memory.save(session_id, messages)
            return AgentResult(output=final, steps=steps)

        raise AgentLoopError(f"超过最大步数 {self._max_steps} 仍未收敛")
