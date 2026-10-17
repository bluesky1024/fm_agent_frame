# ADR-0003：统一事件流与流式输出

- 状态：已接受
- 日期：2026-10-17
- 决策者：仓库所有者 + Claude

## 背景

流式输出、调用链追踪、人工审批、前端推送、评测都需要感知运行过程中的中间状态。现状只有 `Observer` 协议和一个未接线的 `ConsoleTracer`，LLM 调用整包返回，无法复用到上述场景。

## 决策

- `AgentRuntime.run()` 返回 `AsyncIterator[AgentEvent]`。
- 事件类型：`RunStart`、`StepStart`、`ContextBuilt`、`LLMDelta`、`LLMCompleted`、`ToolCallRequested`、`ToolResult`、`RunEnd`、`Error`。
- `run_collect()` 把事件流收集为 `AgentResult`，供不关心中间过程的调用方使用。
- `LLMProvider` 同时提供 `chat()` 与 `stream()`；OpenAI 兼容实现首版即支持流式。
- `Tracer`、UI、评测器、审批器都是事件消费者，不侵入运行时。

## 后果

正面：

- 一条事件流同时支撑流式、trace、SSE、HITL 与评测，避免重复实现。
- 事件序列可被测试精确断言，循环行为可观测。

负面：

- 流式响应需要处理"文本增量 + tool_calls 分片组装"，首版复杂度上升。
- 事件类型一旦扩展，消费者需要兼容新事件（用默认忽略策略缓解）。

## 替代方案

- **回调式 Observer**：难以表达流式与背压，且取消语义弱，未采用。
- **只做非流式**：与业界主流体验差距大，学习价值不足，未采用。
