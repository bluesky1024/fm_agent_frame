# 目标架构

> 状态：已与仓库所有者对齐（2026-10-17）。
> 本文档是 [重构实施计划](./refactor-plan.md) 的依据，关键取舍记录在 `docs/adr/`。
> 定位：学习用的 LLM Agent 框架，教学优先，不追求生产级完备。

## 1. 设计原则

1. **教学优先**：每个模块有清晰协议和单一职责，能被单独阅读、单独替换。生产细节（重试、并发、容错）放在实现层，不污染主线。
2. **可替换内核**：`AgentRuntime` 是唯一的循环引擎；`AgentSpec` 是无状态配置；扩展通过协议注入，而不是继承或修改循环。
3. **流程完备**：每个模块要么有可运行的最小实现，要么有接口 + 空实现，并且**真实接在链路上**，不能是死代码。
4. **单向依赖**：依赖只能自上而下，由 import-linter 守护；禁止 `tools → llm`、`capabilities → interfaces`、`core → 任何内部包`。
5. **框架与应用分离**：通用能力留在框架；具体应用（扫雷）放在 `apps/`。
6. **异步优先**：LLM、工具、运行时全部使用 `async`；同步阻塞调用（截屏、鼠标、文件）通过 `asyncio.to_thread` 隔离。

## 2. 分层全景

```
L5  interfaces      Session · SessionManager · CLI · HTTP server
L4  capabilities    retrieval · multi_agent · guardrails · hitl
                    mcp · sandbox · computer_use · eval
L3  runtime         AgentRuntime · AgentSpec · Middleware · 扩展协议
L2  context         ContextBuilder · Compaction · ContextProvider 协议
L1  llm · tools · memory · obs
L0  core            messages · events · errors · config · 共享类型
```

上层依赖下层。**依赖倒置**：`runtime` 定义钩子与策略协议，`capabilities` 实现它们；`context` 定义 `ContextProvider`，`retrieval` 实现它。因此能力层可以依赖运行时，而运行时不依赖任何具体能力。

## 3. 目录结构

```
src/agent_frame/
├── core/
│   ├── messages.py        # System/User/Assistant/Tool 消息、ToolCall、内容分片
│   ├── events.py          # AgentEvent 及全部事件类型
│   ├── errors.py          # 统一异常体系（可重试 / 致命 / 工具 / 护栏 / 取消）
│   ├── config.py          # pydantic-settings，env/.env 分层配置
│   ├── images.py          # 请求内联图片落盘（llm 与 obs 共用）
│   ├── tokens.py          # 粗略 token 估算
│   └── types.py           # ToolSpec、TokenUsage、AgentResult
├── llm/
│   ├── base.py            # LLMProvider 协议：chat() / stream()
│   └── openai_compat.py   # OpenAI 兼容实现（DeepSeek），流式、用量、重试
├── tools/
│   ├── base.py            # ToolResult、ToolProvider、ToolSandbox 协议（ToolSpec 见 core/types）
│   ├── registry.py        # 注册、查找、列表、导出 schema
│   ├── executor.py        # 参数校验、并行执行、超时、错误分类
│   └── builtin/           # calculator、time
├── memory/
│   ├── base.py            # MemoryStore / Recall / Summarizer / 长期记忆协议
│   ├── conversation.py    # 内存会话历史
│   └── summary_buffer.py  # 摘要 + 滑动窗口压缩
├── obs/
│   ├── tracer.py          # Tracer 协议、ConsoleTracer、JSONLTracer
│   ├── token.py           # token / 成本统计
│   └── logging_setup.py   # 运行日志双路输出
├── context/
│   ├── providers.py       # ContextProvider 协议（记忆召回、检索、用户画像…）
│   ├── builder.py         # 每轮消息装配
│   └── compaction.py      # token 预算与压缩策略
├── runtime/
│   ├── spec.py            # AgentSpec（无状态定义）
│   ├── session.py         # Session 协议（状态归属）
│   ├── policies.py        # Middleware / Guardrail / ApprovalPolicy 协议
│   └── runtime.py         # AgentRuntime：唯一循环引擎
├── capabilities/
│   ├── retrieval/         # Loader/Chunker/Embedder/VectorStore/Retriever/Reranker
│   ├── multi_agent/       # SubTask、TaskDecomposer、SequentialOrchestrator
│   ├── guardrails/        # InputGuard / OutputGuard 空实现
│   ├── hitl/              # ApprovalPolicy 实现（自动批准 / 控制台审批）
│   ├── mcp/               # MCP 客户端协议（仅接口）
│   ├── sandbox/           # 执行沙箱协议（仅接口）
│   └── computer_use/      # 截屏、鼠标、Observer、标注（通用能力）
├── eval/
│   ├── base.py            # EvalCase / Evaluator / EvalReport
│   ├── evaluators.py      # 精确匹配、正则匹配
│   └── suite.py           # 批量执行与报告
└── interfaces/
    ├── session.py         # Session 具体实现、SessionManager
    ├── cli.py             # 交互式命令行
    └── server/            # FastAPI：单端点 + SSE，多会话

apps/minesweeper/          # 棋盘几何、扫雷工具、提示词、启动逻辑
games/minesweeper.py       # 被操作的目标程序，保持不变
examples/                  # 01 基础对话 / 02 工具 / 03 多轮 / 04 扫雷
```

**旧路径已删除**：重构不保留兼容层。循环引擎统一在 `runtime/`，请求装配统一在 `context/`，服务在 `interfaces/server/`，通用桌面能力在 `capabilities/computer_use/`，扫雷应用在 `apps/minesweeper/`。

## 4. 依赖规则

| 包 | 允许依赖 |
|---|---|
| `core` | 仅标准库与第三方库 |
| `llm` / `tools` / `memory` / `obs` | `core` |
| `context` | `core`、`memory` |
| `runtime` | `core`、`llm`、`tools`、`memory`、`obs`、`context` |
| `capabilities.*` / `eval` | 以上全部（用于实现协议、编排与评测流程） |
| `interfaces` | 以上全部 |
| `apps` / `examples` | `agent_frame` 任意公开模块 |

硬性约束：

- `tools` **不得** import `llm`。
- `core` **不得** import 任何内部包。
- `capabilities` **不得** import `interfaces`。
- 框架包 **不得** import `apps` / `examples`。
- 用 import-linter 在本地检查脚本中强制以上规则。

## 5. 核心对象

### AgentSpec（无状态）

```text
AgentSpec
├── name
├── model / provider 配置
├── system_prompt
├── tools: list[ToolSpec]
├── context_providers: list[ContextProvider]
├── memory: MemoryStore
├── max_steps
├── middleware: list[Middleware]
├── input_guards / output_guards
├── approval: ApprovalPolicy
└── metadata
```

### Session（状态归属）

Session 持有运行期间全部可变状态：`id`、`memory`、`state`（工具审批记录、用户偏好等）、`last_run`。`AgentSpec` 本身不可变，可被多个 Session 复用。

### AgentEvent（统一事件流）

```text
RunStart(run_id, session_id, input)
StepStart(step)
ContextBuilt(message_count, token_estimate)
LLMDelta(text)
LLMCompleted(message, usage)
ToolCallRequested(tool_call)
ToolResult(tool_call_id, result | error)
RunEnd(result, usage)
Error(error, recoverable)
```

`AgentRuntime.run()` 返回 `AsyncIterator[AgentEvent]`；`run_collect()` 是收集成 `AgentResult` 的便利封装。`Tracer`、UI、评测、HITL 都消费同一条事件流。

### 扩展协议

| 协议 | 定义位置 | 实现位置 | 用途 |
|---|---|---|---|
| `Middleware` | `runtime/policies.py` | 用户 | `before_llm` / `after_llm` / `before_tool` / `after_tool` |
| `Guardrail` | `runtime/policies.py` | `capabilities/guardrails` | 输入/输出内容检查，可短路 |
| `ApprovalPolicy` | `runtime/policies.py` | `capabilities/hitl` | 工具执行前审批 |
| `ToolSandbox` | `tools/base.py` | `capabilities/sandbox` | 工具执行隔离（首版 no-op） |
| `ToolProvider` | `tools/base.py` | `capabilities/mcp` | 动态提供工具（首版接口） |
| `ContextProvider` | `context/providers.py` | `capabilities/retrieval`、memory recall | 每轮贡献上下文片段 |
| `Tracer` | `obs/tracer.py` | `obs` | 消费事件，输出 trace |
| `MemoryStore` / `Summarizer` | `memory/base.py` | `memory` | 历史存取、压缩 |
| `TaskDecomposer` / `Orchestrator` | `capabilities/multi_agent` | 同包 | 任务拆分与编排 |
| `Evaluator` | `eval/base.py` | `eval` | 结果打分 |
| `Session` | `runtime/session.py` | `interfaces/session.py` | 状态与记忆的载体 |

## 6. 一次运行的流程

```text
用户输入
  │
  ▼
Session 记录用户消息
  │
  ▼
AgentRuntime.run(spec, session, input) ── emit RunStart
  │
  └─ 循环（最多 max_steps 步）
       ├─ ContextBuilder.build(spec, session)
       │    system prompt + 压缩后的历史 + 记忆召回 + 检索片段
       │    （只用于本次调用，不写回历史）        ── emit ContextBuilt
       ├─ 输入护栏检查                            ── 违规则 emit Error / RunEnd
       ├─ LLMProvider.stream(messages, tools)
       │    ├─ 文本增量                           ── emit LLMDelta
       │    └─ 组装完整 Assistant 消息            ── emit LLMCompleted
       ├─ 有 tool_calls？
       │    ├─ 是
       │    │    ├─ ApprovalPolicy 审批
       │    │    ├─ ToolExecutor 校验参数、并行执行、超时、错误分类
       │    │    │    （可恢复错误作为 ToolResult 回填给 LLM）
       │    │    ├─ 结果写入 session 历史
       │    │    └─ 下一步继续
       │    └─ 否
       │         ├─ Assistant 消息写入历史
       │         ├─ 输出护栏检查
       │         └─ emit RunEnd(result, usage)
       └─ 步数超限 / 取消 / 致命错误               ── emit Error + RunEnd
```

关键点：

- **装配结果不落盘**：system prompt、检索片段只在本次请求中存在，避免重复注入历史。
- **工具轮的 assistant 文本保留**：模型在调用工具同时说出的文本会写入历史。
- **失败也落历史**：工具失败以 `ToolResult(error=...)` 回填并记录，保证下一轮上下文完整。
- **取消与超时**：通过 `asyncio.CancelledError` 与每步超时控制，事件流以 `Error` + `RunEnd` 收尾。

## 7. 模块职责与首版深度

| 模块 | 职责 | 首版深度 |
|---|---|---|
| `core` | 消息、事件、错误、配置、共享类型 | 完整 |
| `llm` | 供应商协议、OpenAI 兼容、流式、用量、重试 | 完整 |
| `tools` | 协议自包含、注册、校验、并行、超时、错误分类 | 完整（沙箱/MCP 仅协议） |
| `runtime` | 循环、步骤控制、中间件、审批、事件、取消 | 完整 |
| `context` | 每轮装配、token 预算、压缩 | 完整（首版确定性摘要 + 滑动窗口） |
| `memory` | 会话历史、摘要滑窗、长期记忆协议 | 短时完整；长期仅协议 |
| `obs` | 事件消费者、Console/JSONL trace、token 统计 | 最小闭环 |
| `capabilities/retrieval` | RAG 流水线 | 最小闭环（内存向量库 + 确定性假 embedder） |
| `capabilities/multi_agent` | 任务拆分、顺序编排 | 最小实现（并行/交接仅协议） |
| `capabilities/guardrails` | 输入/输出护栏 | 接口 + 空实现，链路接线 |
| `capabilities/hitl` | 工具审批 | 自动批准实现 + 控制台审批示例 |
| `capabilities/mcp` | MCP 工具接入 | 仅接口 |
| `capabilities/sandbox` | 工具执行隔离 | 仅接口 + no-op |
| `capabilities/computer_use` | 截屏、鼠标、观察、标注 | 完整（通用能力） |
| `eval` | 用例、评测器、批量报告 | 最小闭环 |
| `interfaces/session` | Session、SessionManager | 完整 |
| `interfaces/cli` | 交互式命令行 | 最小实现 |
| `interfaces/server` | HTTP + SSE、多会话 | 最小实现 |
| `apps/minesweeper` | 扫雷应用与工具 | 完整（从现有代码迁移） |

## 8. 配置、错误与可观测

- **配置**：`core/config.py` 统一用 pydantic-settings 读取 env/.env；应用不得再传裸 dict。日志目录、模型、最大步数、超时、token 预算都在配置中。
- **错误分层**：`ConfigError`、`LLMError(retryable)`、`ToolError(recoverable)`、`GuardrailViolation`、`StepLimitExceeded`、`Cancelled`。可恢复错误回填给 LLM，致命错误终止本次运行。
- **可观测**：运行日志与 LLM 原始交互日志保持现有双路输出（`log/agent.log`、`log/llm.log`）；新增事件驱动的 JSONL trace（默认 `log/trace.jsonl`），记录每步耗时、工具调用、token 用量。Trace 不依赖具体 provider。

## 9. 应用边界

- 框架只提供**通用计算机使用能力**：截屏、鼠标、观察、标注。不包含任何游戏规则。
- 扫雷的棋盘几何、点击/插旗/重开工具、提示词、启动逻辑全部在 `apps/minesweeper/`。
- `games/minesweeper.py` 保持不变，继续作为被操作的目标程序。
- 框架包禁止 import `apps/`；应用通过公开 API 组装 Runtime、Spec 与工具。

## 10. 非目标

- 不做多租户、鉴权、分布式执行。
- 不实现完整 MCP、沙箱、向量数据库；只提供可替换接口与最小实现。
- 不追求多供应商矩阵，首版只保留 OpenAI 兼容实现。
- 不做前端 UI；`interfaces/server` 只提供最小 HTTP/SSE 能力。
- 不保留旧 API 兼容层；examples 与测试随重构同步更新。

## 11. 重构前问题与当前方案

以下问题均已在本次重构中解决：

| 重构前问题 | 当前方案 |
|---|---|
| 循环与 Agent 定义混在一个类里 | `AgentSpec` 与 `AgentRuntime` 分离 |
| 工具层反向依赖 LLM 层 | `ToolSpec` 自包含，`tools` 只依赖 `core` |
| 桌面能力与应用逻辑混在框架内并循环导入 | 通用能力入 `capabilities/computer_use`，应用逻辑入 `apps/` |
| system prompt 每轮写入历史 | 由 `context` 装配，不写回历史 |
| 工具轮丢弃 assistant 文本 | 完整保存 assistant 消息 |
| 工具串行、无校验、无超时 | `ToolExecutor` 校验 + 并行 + 超时 + 错误分类 |
| 无流式 | `LLMProvider.stream()` + 事件流 |
| 配置散落、应用使用裸 dict | 统一 `core/config.py`，应用配置显式传入 |
| Tracer 未接线 | 事件流驱动的 Tracer 真实接线 |
| 同步阻塞调用混入 async | `asyncio.to_thread` 隔离 |
| 无依赖方向守护 | import-linter + 本地检查脚本 |
