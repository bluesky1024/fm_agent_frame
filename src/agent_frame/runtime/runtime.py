"""AgentRuntime：唯一的 Agent 循环引擎。

一次运行的流程见 architecture.md §6：
装配请求视图 → 流式调用 LLM → 有工具调用则执行并回填 → 否则结束。
装配结果（system、提供者片段）不写回 Session 历史；工具轮 assistant 文本与
失败结果都会落历史。

中间件顺序遵循 ADR-0002：before 按注册顺序执行，after 逆序执行。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Sequence

from agent_frame.context.builder import ContextBuilder
from agent_frame.context.compaction import compact_if_needed, history_view
from agent_frame.core.errors import (
    Cancelled,
    GuardrailViolation,
    LLMError,
    StepLimitExceeded,
    ToolError,
)
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
from agent_frame.runtime.policies import Guardrail, RunContext
from agent_frame.runtime.session import Session
from agent_frame.runtime.spec import AgentSpec
from agent_frame.tools import ToolExecutor, ToolRegistry, ToolResult

logger = logging.getLogger("agent_frame.runtime")


class AgentRuntime:
    """执行 AgentSpec 的循环引擎。"""

    async def run(
        self, spec: AgentSpec, session: Session, user_input: str
    ) -> AsyncIterator[AgentEvent]:
        """执行一轮对话，把事件分发给 Tracer 并同时输出给调用方。"""
        tracers = list(spec.tracers)
        async for event in self._run(spec, session, user_input):
            for tracer in tracers:
                try:
                    tracer.on_event(event)
                except Exception:  # noqa: BLE001 - 追踪失败不应中断运行
                    logger.exception("Tracer 处理事件失败")
            yield event

    async def _run(
        self, spec: AgentSpec, session: Session, user_input: str
    ) -> AsyncIterator[AgentEvent]:
        """执行一轮对话，以事件流输出全过程。"""
        run_id = uuid.uuid4().hex[:12]
        yield RunStart(run_id=run_id, session_id=session.id, input=user_input)

        if spec.memory is not None:
            session.memory = spec.memory
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

                run_context = RunContext(
                    run_id=run_id,
                    session_id=session.id,
                    spec_name=spec.name,
                    step=step,
                    usage=total_usage,
                )
                if step == 0 and spec.input_guards:
                    allowed, reason, checked = await _check_guards(
                        spec.input_guards, user_input, run_context
                    )
                    if not allowed:
                        result_value = self._make_result("", total_usage, steps_taken)
                        input_error = GuardrailViolation(f"输入被护栏拦截: {reason}")
                        for event in self._finish(session, result_value, str(input_error)):
                            yield event
                        return
                    if checked != user_input:
                        user_input = checked
                        session.history[-1] = Message.user(checked)
                        await session.memory.save(session.id, session.history)

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

                messages = context.messages
                for middleware in spec.middleware:
                    messages = await middleware.before_llm(run_context, messages)

                completion: ChatResult | None = None
                async for chunk in spec.llm.stream(messages, tool_specs, model=spec.model):
                    if chunk.text_delta:
                        yield LLMDelta(text=chunk.text_delta)
                    if chunk.result is not None:
                        completion = chunk.result
                if completion is None:
                    raise LLMError("LLM 流式调用未返回最终结果")

                for middleware in reversed(spec.middleware):
                    completion = await middleware.after_llm(run_context, completion)

                steps_taken += 1
                total_usage = total_usage + completion.usage

                if not completion.tool_calls and spec.output_guards:
                    allowed, reason, checked = await _check_guards(
                        spec.output_guards, completion.content or "", run_context
                    )
                    if not allowed:
                        # 被拦截的内容不进入事件结果，也不写回历史
                        yield LLMCompleted(
                            message=Message.assistant(content=None),
                            usage=completion.usage,
                        )
                        result_value = self._make_result("", total_usage, steps_taken)
                        output_error = GuardrailViolation(f"输出被护栏拦截: {reason}")
                        for event in self._finish(session, result_value, str(output_error)):
                            yield event
                        return
                    if checked != (completion.content or ""):
                        completion = completion.model_copy(update={"content": checked})

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
                    result_value = self._make_result(
                        completion.content or "", total_usage, steps_taken
                    )
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

                result_map: dict[int, ToolResult] = {}
                to_execute: list[tuple[int, ToolCall]] = []
                for index, call in enumerate(calls):
                    if spec.approval is None:
                        to_execute.append((index, call))
                        continue
                    decision = await spec.approval.approve(call, context=run_context)
                    session.state.setdefault("approvals", []).append(
                        {
                            "call_id": call.id,
                            "name": call.name,
                            "approved": decision.approved,
                            "reason": decision.reason,
                        }
                    )
                    if decision.approved:
                        to_execute.append((index, call))
                    else:
                        result_map[index] = ToolResult(
                            tool_call_id=call.id,
                            name=call.name,
                            error=f"工具调用被拒绝: {decision.reason or '未批准'}",
                            error_type="approval",
                            recoverable=True,
                        )

                try:
                    executed = await executor.execute_many([call for _, call in to_execute])
                except ToolError as exc:
                    # 致命错误：补齐每个调用的 tool 消息，保持历史可继续使用
                    for index, call in enumerate(calls):
                        tool_result = result_map.get(index) or ToolResult(
                            tool_call_id=call.id,
                            name=call.name,
                            error=str(exc),
                            error_type="fatal",
                            recoverable=False,
                        )
                        yield ToolResultEvent(
                            tool_call_id=call.id,
                            name=call.name,
                            content=tool_result.content,
                            error=tool_result.error,
                        )
                        await self._append(session, _tool_message(call, tool_result))
                    result_value = self._make_result(last_text, total_usage, steps_taken)
                    for event in self._finish(session, result_value, str(exc), recoverable=False):
                        yield event
                    return
                for (index, _), tool_result in zip(to_execute, executed):
                    result_map[index] = tool_result
                tool_results = [result_map[index] for index in range(len(calls))]

                for call, tool_result in zip(calls, tool_results):
                    for middleware in reversed(spec.middleware):
                        tool_result = await middleware.after_tool(run_context, tool_result)
                    yield ToolResultEvent(
                        tool_call_id=call.id,
                        name=call.name,
                        content=tool_result.content,
                        error=tool_result.error,
                    )
                    await self._append(session, _tool_message(call, tool_result))

            result_value = self._make_result(last_text, total_usage, steps_taken)
            limit_error = StepLimitExceeded(f"超过最大步数 {spec.max_steps} 仍未收敛")
            for event in self._finish(session, result_value, str(limit_error)):
                yield event
        except asyncio.CancelledError:
            result_value = self._make_result(last_text, total_usage, steps_taken)
            cancel_error = Cancelled("运行已取消")
            for event in self._finish(session, result_value, str(cancel_error)):
                yield event
            raise
        except LLMError as exc:
            result_value = self._make_result(last_text, total_usage, steps_taken)
            for event in self._finish(session, result_value, str(exc), recoverable=exc.retryable):
                yield event

    async def _append(self, session: Session, message: Message) -> None:
        """把消息写入持久历史（记忆），供下一轮重新加载。"""
        session.history.append(message)
        await session.memory.save(session.id, session.history)

    def _make_result(self, output: str, usage: TokenUsage, steps: int) -> AgentResult:
        return AgentResult(output=output, usage=usage, steps=steps)

    def _finish(
        self,
        session: Session,
        result: AgentResult,
        error: str,
        *,
        recoverable: bool = False,
    ) -> list[AgentEvent]:
        session.last_run = result
        return [ErrorEvent(error=error, recoverable=recoverable), RunEnd(result=result)]

    async def run_collect(self, spec: AgentSpec, session: Session, user_input: str) -> AgentResult:
        """跑完一轮并把事件流收集为结构化结果。"""
        result = AgentResult(output="")
        async for event in self.run(spec, session, user_input):
            if isinstance(event, RunEnd):
                result = event.result
        return result


async def _check_guards(
    guards: Sequence[Guardrail],
    text: str,
    context: RunContext,
) -> tuple[bool, str | None, str]:
    """依次执行护栏；任一拒绝即返回，replacement 会覆盖后续文本。"""
    current = text
    for guard in guards:
        decision = await guard.check(current, context=context)
        if not decision.allowed:
            return False, decision.reason or "未说明原因", current
        if decision.replacement is not None:
            current = decision.replacement
    return True, None, current


def _tool_message(call: ToolCall, result: ToolResult) -> Message:
    if result.ok:
        return Message.tool(tool_call_id=call.id, content=result.content or "", name=call.name)
    return Message.tool(
        tool_call_id=call.id,
        content=f"工具执行出错: {result.error}",
        name=call.name,
    )
