# ADR-0002：AgentRuntime 与 AgentSpec 分离

- 状态：已接受
- 日期：2026-10-17
- 决策者：仓库所有者 + Claude

## 背景

现状中 `ToolUseAgent` 同时承担"agent 是什么"（提示词、工具、记忆）与"循环怎么跑"（调用 LLM、执行工具、步数控制）。新增 plan-execute、reflection 等模式时只能复制或继承循环，导致行为散落。

## 决策

- `AgentSpec` 是**无状态**定义：提示词、工具、上下文提供者、记忆、步数上限、中间件、护栏、审批策略。
- `AgentRuntime` 是**唯一**循环引擎：步骤控制、LLM 调用、工具执行、事件发射、取消与超时。
- `AgentSpec` 与 `AgentRuntime` 通过 `Middleware` / `Guardrail` / `ApprovalPolicy` 协议扩展；未来新模式通过新增中间件或策略实现，不修改循环。
- 对外入口为 `AgentRuntime.run(spec, session, input)`。

## 后果

正面：

- 循环只有一份，行为一致，易测试。
- spec 可序列化、可复用、可被多个会话共享。
- 新模式（计划、反思）作为策略叠加，教学上界限清楚。

负面：

- 比"一个 Agent 子类搞定"多一层概念，首次阅读需要理解 spec/runtime/session 三者关系。
- 中间件顺序需要明确定义（按注册顺序执行 before，逆序执行 after）。

## 替代方案

- **保留 Agent 子类继承**：循环重复、扩展靠重写，未采用。
- **完全事件驱动状态机**：教学复杂度偏高，首版以事件流 + 循环实现，后续可演进。
