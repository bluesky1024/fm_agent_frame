"""交互式命令行：逐行读取输入，用同一个 Runtime/Session 跑多轮对话。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from agent_frame.runtime.runtime import AgentRuntime
from agent_frame.runtime.session import Session
from agent_frame.runtime.spec import AgentSpec


class ChatCLI:
    """最小交互循环；输入函数可注入，便于测试。"""

    def __init__(
        self,
        runtime: AgentRuntime,
        spec: AgentSpec,
        session: Session,
        *,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ) -> None:
        self._runtime = runtime
        self._spec = spec
        self._session = session
        self._input = input_fn
        self._output = output_fn

    async def run(self) -> None:
        self._output("进入交互模式（输入 exit / quit 退出）。")
        while True:
            try:
                user_input = await asyncio.to_thread(self._input, "\n你> ")
            except (EOFError, KeyboardInterrupt):
                self._output("\n再见！")
                return

            if not user_input.strip():
                continue
            if user_input.strip().lower() in ("exit", "quit"):
                self._output("再见！")
                return

            result = await self._runtime.run_collect(self._spec, self._session, user_input)
            self._output(f"Agent> {result.output}")
