# fm_agent_frame

从零手写的 **Agent 编排框架**，用于学习 AI Agent 的核心机制。

不依赖 LangChain / LangGraph，用 Python 3.12 + async；LLM 走 OpenAI 兼容协议（默认 DeepSeek）。目标是「总-分」式学习：先看清全景（有哪些模块、各自干什么、如何协作），再逐个模块深入。

## 分层全景

```text
interfaces      Session · SessionManager · HTTP/SSE 服务
capabilities    retrieval · multi_agent · guardrails · hitl · mcp · sandbox · computer_use
eval            用例 · 评测器 · 批量报告
runtime         AgentRuntime · AgentSpec · Middleware · 扩展协议
context         ContextBuilder · 上下文提供者 · 摘要滑窗
llm · tools · memory · obs
core            messages · events · errors · config · 共享类型
```

上层依赖下层，由 import-linter 自动守护。`AgentRuntime` 是唯一循环引擎，`AgentSpec` 是无状态定义，`Session` 持有状态，统一事件流承载流式、追踪、审批与评测。

## 目录结构

```text
src/agent_frame/
├── core/            消息、事件、错误、配置、token 估算
├── llm/             LLMProvider 协议；OpenAI 兼容的整包与流式实现
├── tools/           自包含工具协议、注册表、执行器（校验/并行/超时/错误分类）
├── memory/          会话记忆；摘要 + 滑动窗口；长期记忆协议
├── obs/             事件驱动 Tracer（Console/JSONL）、token 与耗时统计
├── context/         每轮请求装配与压缩策略
├── runtime/         AgentRuntime、AgentSpec、Session 协议、中间件/护栏/审批协议
├── capabilities/    retrieval · multi_agent · guardrails · hitl · mcp · sandbox · computer_use
├── eval/            精确/正则评测器、批量评测套件
└── interfaces/      SessionManager、FastAPI 聊天端点与 SSE

apps/minesweeper/    棋盘几何、工具、提示词、观察与启动逻辑
games/minesweeper.py 被操作的目标程序（保持不变）
examples/            01 基础对话 / 02 工具 / 03 多轮 / 04 扫雷
```

## 快速开始

```bash
# 1. 激活环境并安装（桌面与 HTTP 能力按需加 [dev,desktop,server]）
conda activate py312
pip install -e ".[dev]"

# 2. 配置 API key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-xxx

# 3. 基础对话：观察完整事件流
python examples/01_hello_llm.py

# 4. 工具 Agent：流式事件 + log/trace.jsonl
python examples/02_tool_agent.py

# 5. 交互式多轮对话（输入 exit 退出）
python examples/03_interactive.py

# 6. 扫雷视觉 Agent 自动对局（需 pip install -e ".[desktop]"）
MODEL=deepseek-flash python examples/04_minesweeper_autoplay.py
```

## 一次运行发生了什么

```text
run(spec, session, input)
  → Session 记录用户消息
  → 每步：ContextBuilder 装配请求视图
       system + 记忆召回/检索片段 + 压缩后的历史
       （装配结果不写回持久历史）
  → LLMProvider.stream() → LLMDelta* → LLMCompleted
  → 有 tool_calls：审批 → ToolExecutor 校验/并行/超时 → ToolResult 回填历史
  → 无 tool_calls：输出护栏 → RunEnd(result, usage)
```

事件类型：`RunStart`、`StepStart`、`ContextBuilt`、`LLMDelta`、`LLMCompleted`、`ToolCallRequested`、`ToolResult`、`RunEnd`、`Error`。Tracer、SSE、评测与审批都消费同一条事件流。

## 模块深度

| 模块 | 首版深度 |
|---|---|
| `core` / `llm` / `tools` / `runtime` / `context` / `session` | 完整 |
| `obs` | 最小闭环：Console/JSONL trace、token 与耗时统计 |
| `memory` | 短时记忆与摘要滑窗完整；长期记忆仅协议 |
| `capabilities/retrieval` | 最小闭环：确定性 embedder + 内存向量库 + 上下文提供者 |
| `capabilities/multi_agent` | 顺序编排实现；并行与交接仅协议 |
| `capabilities/guardrails` / `hitl` | 空实现 + 关键词/控制台审批，真实接线 |
| `capabilities/mcp` / `sandbox` | 协议 + 适配器/no-op，真实接线 |
| `capabilities/computer_use` | 完整：截屏、鼠标、观察、标注 |
| `eval` / `interfaces/server` | 最小闭环 |
| `apps/minesweeper` | 完整应用，含假 LLM e2e |

## 本地检查

```bash
python scripts/check.py
```

依次运行 `ruff check`、`ruff format --check`、`mypy`（core/llm/tools/runtime 严格）、`lint-imports` 与 `pytest`。

依赖规则由 import-linter 强制：

- `tools` 不依赖 `llm`
- `core` 不依赖任何内部模块
- `capabilities` 不依赖 `interfaces`
- 框架不依赖 `apps` / `examples` / `games`

## 调试日志与 trace

- **主日志**：控制台（`LOG_CONSOLE=false` 可关闭）+ `log/agent.log`，级别由 `LOG_LEVEL` 控制
- **LLM 交互日志**：`log/llm.log` 始终全量记录请求/回包；内联截图落盘到 `log/pic/*.png`
- **事件 trace**：示例 02 通过 `JSONLTracer` 写出 `log/trace.jsonl`，每行一个事件 JSON

```bash
LOG_LEVEL=DEBUG python examples/02_tool_agent.py
```

## 学习路线

建议顺序：`core → llm/tools → runtime → context/memory → capabilities → interfaces → apps`。
详见 [docs/roadmap.md](docs/roadmap.md)、[docs/architecture.md](docs/architecture.md) 与 `docs/adr/`。

## 扫雷应用

- 目标程序 `games/minesweeper.py` 是本仓库自带的固定窗口扫雷，几何由 `board_config()` 自报，无需校准。
- 框架只提供通用计算机使用能力（截屏/鼠标/观察/标注）；棋盘几何、工具、提示词与启动逻辑在 `apps/minesweeper/`。
- macOS 需在「系统设置 → 隐私与安全性 → 辅助功能」授权终端/Python 控制鼠标。
- 详细调用流程见 [docs/minesweeper-agent-flow.md](docs/minesweeper-agent-flow.md)。

## 真实 API 人工验收

自动测试全部使用 fake LLM；真实 API 的验收步骤见 [docs/acceptance.md](docs/acceptance.md)。
