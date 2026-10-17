"""AgentRuntime：唯一的 Agent 循环引擎。

一次运行的流程见 architecture.md §6：
装配请求视图 → 流式调用 LLM → 有工具调用则执行并回填 → 否则结束。
装配结果（system、提供者片段）不写回 Session 历史；工具轮 assistant 文本与
失败结果都会落历史。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

from agent_frame.context.builder import ContextBuilder
from agent_frame.context.compaction import compact_if_needed, history_view
from agent_frame.core.errors import LLMError, ToolError
from agent_frame.core.events import (
    AgentEvent,
    ContextBuilt,
    LLMCompleted,
    LLMDelta,
    RunEnd,
    RunStart,
    StepStart,
    ToolCallRequested,
)
from agent_frame.core.events import (
    Error as ErrorEvent,
)
from agent_frame.core.events import (
    ToolResult as ToolResultEvent,
)
from agent_frame.core.messages import Message, ToolCall
from agent_frame.core.types import AgentResult, TokenUsage
from agent_frame.llm.base import ChatResult
from agent_frame.runtime.policies import RunContext
from agent_frame.runtime.session import Session
from agent_frame.runtime.spec import AgentSpec
from agent_frame.tools import ToolExecutor, ToolRegistry, ToolResult


class AgentRuntime:
    """执行 AgentSpec 的循环引擎。"""

    async def run(
        self, spec: AgentSpec, session: Session, user_input: str
    ) -> AsyncIterator[AgentEvent]:
        """执行一轮对话，以事件流输出全过程。"""
        run_id = uuid.uuid4().hex[:12]
        yield RunStart(run_id=run_id, session_id=session.id, input=user_input)

        session.history = await session.memory.load(session.id)
        await self._append(session, Message.user(user_input))

        builder = ContextBuilder(spec.context_providers)
        executor = ToolExecutor(
            ToolRegistry(list(spec.tools)),
            providers=spec.tool_providers,
            timeout=spec.tool_timeout,
            sandbox=spec.sandbox,
        )
        tool_specs = await executor.tool_specs() or None

        steps_taken = 0
        total_usage = TokenUsage()
        last_text = ""

        try:
            for step in range(spec.max_steps):
                yield StepStart(step=step)

                await compact_if_needed(
                    session.memory,
                    session.id,
                    token_threshold=spec.context_token_budget,
                    keep_last=spec.compaction_keep_last,
                )
                history = await history_view(session.memory, session.id) or session.history
                context = await builder.build(
                    system_prompt=spec.system_prompt,
                    history=history,
                    user_input=user_input,
                    session_id=session.id,
                )
                yield ContextBuilt(
                    message_count=len(context.messages),
                    token_estimate=context.token_estimate,
                )

                run_context = RunContext(
                    run_id=run_id,
                    session_id=session.id,
                    spec_name=spec.name,
                    step=step,
                    usage=total_usage,
                )
                messages = context.messages
                for middleware in spec.middleware:
                    messages = await middleware.before_llm(run_context, messages)

                completion: ChatResult | None = None
                async for chunk in spec.llm.stream(messages, tool_specs):
                    if chunk.text_delta:
                        yield LLMDelta(text=chunk.text_delta)
                    if chunk.result is not None:
                        completion = chunk.result
                if completion is None:
                    raise LLMError("LLM 流式调用未返回最终结果")

                for middleware in spec.middleware:
                    completion = await middleware.after_llm(run_context, completion)

                steps_taken += 1
                total_usage = total_usage + completion.usage
                last_text = completion.content or last_text
                yield LLMCompleted(
                    message=Message.assistant(
                        content=completion.content,
                        tool_calls=completion.tool_calls,
                    ),
                    usage=completion.usage,
                )

                # 工具轮的 assistant 文本随 tool_calls 一起落历史
                await self._append(
                    session,
                    Message.assistant(content=completion.content, tool_calls=completion.tool_calls),
                )

                if not completion.tool_calls:
                    output = completion.content or ""
                    result_value = AgentResult(output=output, usage=total_usage, steps=steps_taken)
                    session.last_run = result_value
                    yield RunEnd(result=result_value)
                    return

                calls: list[ToolCall] = []
                for tool_call in completion.tool_calls:
                    call = tool_call
                    for middleware in spec.middleware:
                        call = await middleware.before_tool(run_context, call)
                    calls.append(call)
                    yield ToolCallRequested(tool_call=call)

                try:
                    tool_results = await executor.execute_many(calls)
                except ToolError as exc:
                    yield ErrorEvent(error=str(exc), recoverable=False)
                    result_value = AgentResult(
                        output=last_text, usage=total_usage, steps=steps_taken
                    )
                    session.last_run = result_value
                    yield RunEnd(result=result_value)
                    return

                for call, tool_result in zip(calls, tool_results):
                    for middleware in spec.middleware:
                        tool_result = await middleware.after_tool(run_context, tool_result)
                    yield ToolResultEvent(
                        tool_call_id=call.id,
                        name=call.name,
                        content=tool_result.content,
                        error=tool_result.error,
                    )
                    await self._append(session, _tool_message(call, tool_result))

            result_value = AgentResult(output=last_text, usage=total_usage, steps=steps_taken)
            session.last_run = result_value
            yield ErrorEvent(
                error=f"超过最大步数 {spec.max_steps} 仍未收敛",
                recoverable=False,
            )
            yield RunEnd(result=result_value)
        except asyncio.CancelledError:
            result_value = AgentResult(output=last_text, usage=total_usage, steps=steps_taken)
            session.last_run = result_value
            yield ErrorEvent(error="运行已取消", recoverable=False)
            yield RunEnd(result=result_value)
            raise
        except LLMError as exc:
            result_value = AgentResult(output=last_text, usage=total_usage, steps=steps_taken)
            session.last_run = result_value
            yield ErrorEvent(error=str(exc), recoverable=exc.retryable)
            yield RunEnd(result=result_value)

    async def _append(self, session: Session, message: Message) -> None:
        """把消息写入持久历史（记忆），供下一轮重新加载。"""
        session.history.append(message)
        await session.memory.save(session.id, session.history)

    async def run_collect(self, spec: AgentSpec, session: Session, user_input: str) -> AgentResult:
        """跑完一轮并把事件流收集为结构化结果。"""
        result = AgentResult(output="")
        async for event in self.run(spec, session, user_input):
            if isinstance(event, RunEnd):
                result = event.result
        return result


def _tool_message(call: ToolCall, result: ToolResult) -> Message:
    if result.ok:
        return Message.tool(tool_call_id=call.id, content=result.content or "", name=call.name)
    return Message.tool(
        tool_call_id=call.id,
        content=f"工具执行出错: {result.error}",
        name=call.name,
    )
