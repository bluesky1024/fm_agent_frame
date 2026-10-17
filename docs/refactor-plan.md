# 重构实施计划

> 依据：[目标架构](./architecture.md)、`docs/adr/`。
> 原则：每个阶段结束时仓库可运行、`pytest` 全绿；扫雷在 P0–P3 允许离线，P4 恢复；不保留旧 API 兼容层。

## 阶段总览

| 阶段 | 主题 | 交付物 | 验收门槛 |
|---|---|---|---|
| P0 | 基线 | 目录骨架、本地工具链、依赖规则、测试基线 | 检查脚本可运行；现有测试全绿；行为不变 |
| P1 | 内核 | `core`、流式 `llm`、重构后的 `tools`、`runtime` | 新内核测试通过；examples 01–03 重写可跑 |
| P2 | 上下文与会话 | `context`、`memory`、`interfaces/session` | 装配/压缩/会话测试通过；两个历史 bug 修复 |
| P3 | 能力层 | `obs`、`retrieval`、`eval`、`multi_agent`、空实现能力、`server` | 每个能力有最小闭环测试；事件流被真实消费 |
| P4 | 计算机使用与应用 | `capabilities/computer_use`、`apps/minesweeper` | fake-LLM 全流程 e2e 通过；旧路径删除 |
| P5 | 收尾 | README、roadmap、examples 04、文档定稿 | 全套检查通过；达到"基本完备版本"定义 |

## 本地工具链

开发依赖写入 `pyproject.toml` 的 `[project.optional-dependencies].dev`：

```bash
pip install -e ".[dev,desktop,server]"
```

检查脚本 `scripts/check.py` 依次执行（跨平台，Windows/macOS 一致）：

```text
python -m ruff check .
python -m ruff format --check .
python -m mypy
lint-imports
python -m pytest
```

`python scripts/check.py` 会按上述顺序执行，并自动定位 `lint-imports`。`games/` 是目标程序，排除在 ruff 之外。

不启用 GitHub Actions；在本地与需要时手动执行。后续若需要 CI，直接复用以上命令。

mypy 严格模式在 P0 覆盖 `core` 与 `runtime`；`llm` 与 `tools` 随票 02/03 重构后纳入严格检查。其余包首版宽松。

## P0 基线

- [ ] 创建 `docs/architecture.md`、`docs/refactor-plan.md`、`docs/adr/0001–0007`。
- [ ] 创建新包骨架（仅 `__init__.py`），旧代码保持原位。
- [ ] 在 `pyproject.toml` 增加 `ruff`、`mypy`、`import-linter` 开发依赖与配置。
- [ ] 配置 import-linter 契约：分层依赖、禁止反向依赖、禁止 `tools → llm`。
- [ ] 新增 `scripts/check.py`。
- [ ] 记录基线：运行现有 `pytest`，确认全绿（当前 78 个用例，含修复后的 Windows 路径断言）。

**验收**：`python scripts/check.py` 通过；旧 examples 行为不变。

## P1 内核

- [ ] `core/messages.py`、`core/errors.py`、`core/config.py` 从旧模块迁移；新增 `core/events.py`、`core/types.py`。
- [ ] `llm/base.py` 定义 `chat()` 与 `stream()`；`openai_compat.py` 实现流式、用量提取、重试配置。
- [ ] `tools/base.py` 定义自包含 `ToolSpec` / `ToolResult` / `ToolProvider` / `ToolSandbox`；删除对 `llm` 的依赖。
- [ ] `tools/registry.py` 与 `tools/executor.py`：JSON Schema 校验、同批工具并行、超时、错误分类。
- [ ] `tools/builtin/` 迁移 calculator、time。
- [ ] `runtime/spec.py`、`runtime/session.py`（协议）、`runtime/policies.py`、`runtime/runtime.py`：事件流、步骤控制、中间件、取消、步数上限。
- [ ] 重写 `examples/01_basic_chat.py`、`02_tool_agent.py`、`03_interactive.py`。
- [ ] 新增/重写测试：消息、流式分片组装、工具校验与并行、runtime 事件序列。

**验收**：核心四包类型检查通过；无 `tools → llm` 依赖；examples 01–03 可跑；测试全绿。

## P2 上下文与会话

- [ ] `context/providers.py` 定义 `ContextProvider`；`context/builder.py` 负责每轮装配；`context/compaction.py` 负责 token 预算。
- [ ] `memory/conversation.py` 迁移并适配新消息模型；`memory/summary_buffer.py` 实现摘要 + 滑动窗口。
- [ ] `interfaces/session.py` 实现 `Session` 与 `SessionManager`。
- [ ] 修复 system prompt 重复写入历史的问题。
- [ ] 修复工具轮 assistant 文本被丢弃的问题。
- [ ] 工具失败结果写入历史。
- [ ] 测试：装配不落盘、工具轮文本保留、压缩触发、多轮会话隔离。

**验收**：上述测试通过；03 多轮对话可用；历史记录中不再出现重复 system 消息。

## P3 能力层

- [ ] `obs/tracer.py`：`Tracer` 协议、`ConsoleTracer`、`JSONLTracer`；在 runtime 中接线。
- [ ] `obs/token.py`：按事件累计 token 与耗时。
- [ ] `capabilities/retrieval`：Loader → Chunker → Embedder → VectorStore → Retriever → Reranker；首版内存实现与确定性假 embedder，实现 `ContextProvider`。
- [ ] `capabilities/multi_agent`：`SubTask`、`TaskDecomposer` 协议、`SequentialOrchestrator` 最小实现。
- [ ] `capabilities/guardrails`：输入/输出护栏协议与空实现，接入 runtime。
- [ ] `capabilities/hitl`：`AutoApprove` 与 `ConsoleApprove`，接入工具执行前审批。
- [ ] `capabilities/mcp`、`capabilities/sandbox`：协议 + no-op 实现，接入 `ToolProvider` / `ToolExecutor`。
- [ ] `eval/`：精确匹配、正则匹配、批量报告。
- [ ] `interfaces/server/`：单聊天端点 + SSE 流式输出 + 多会话。
- [ ] 每个能力至少一个最小闭环测试。

**验收**：trace 文件产生；eval 能对 fake LLM 跑批并输出报告；no-op 能力不改变主流程行为；检索结果出现在装配消息中。

## P4 计算机使用与应用

- [ ] `desktop/` 的 screen、mouse、observer、annotate 迁入 `capabilities/computer_use/`；同步调用改为 `asyncio.to_thread`。
- [ ] 新建 `apps/minesweeper/`：棋盘几何、点击/插旗/重开工具、提示词、启动器、应用配置。
- [ ] 删除 `desktop/minesweeper.py` 与 `tools/desktop/` 的旧路径，消除循环导入。
- [ ] 新增 fake-LLM 的扫雷全流程 e2e 测试：启动 → 截屏 → 工具调用 → 状态推进 → 结束。
- [ ] 更新 `examples/04_minesweeper_autoplay.py` 指向 `apps/minesweeper`。

**验收**：e2e 测试通过；import-linter 全绿；`games/minesweeper.py` 未被修改。

## P5 收尾

- [ ] 重写 `README.md` 与 `docs/roadmap.md`，与最终目录一致。
- [ ] 更新 `docs/architecture.md` 的模块深度与协议细节。
- [ ] 补充 ADR（如实施中出现新的关键取舍）。
- [ ] 运行 `scripts/check.py` 全套检查。
- [ ] 清理旧模块、旧示例路径与失效文档引用。

**验收**：达到下方"基本完备版本"定义。

## 基本完备版本定义

以下全部满足后，才安排真实 API 人工验收：

1. `pytest` 全绿，包含 fake LLM 的扫雷 e2e。
2. `examples/01–04` 全部可运行（01–03 不依赖真实 API 的 fake 变体或真实 API 均可）。
3. `ruff`、`mypy`、`import-linter` 全部通过。
4. 每个能力模块有最小实现或空实现，且在 runtime/context/session 链路中真实接线。
5. 事件流、trace 文件、token 统计在示例中可见。
6. 旧路径已删除，README 与目录结构一致。

## 人工验收清单（真实 API，重构完成后）

- [ ] `examples/02_tool_agent.py`：工具调用与流式输出正常。
- [ ] `examples/03_interactive.py`：多轮对话，历史正确、无重复 system。
- [ ] `examples/04_minesweeper_autoplay.py`：真实模型完成一局扫雷。
- [ ] 工具参数错误：错误信息回填给模型，模型能纠正。
- [ ] 工具执行异常：流程不中断，失败结果进入历史。
- [ ] 步数超限与取消：事件流以 `Error` + `RunEnd` 正常收尾。
- [ ] 日志：`log/agent.log`、`log/llm.log`、`log/trace.jsonl` 均生成且内容合理。

## 风险与应对

| 风险 | 应对 |
|---|---|
| 事件流与流式首版复杂度高 | 先实现非流式 `chat()` 兜底；流式用 fake 分片测试组装；`run_collect()` 降低使用门槛 |
| 迁移期间扫雷不可用 | 已确认接受；P4 一次性迁移，避免中途两套并存 |
| 能力层范围膨胀 | 严格按第 7 节深度表执行，超出范围的只留协议 |
| import-linter 与可选依赖冲突 | 契约只约束内部包，忽略第三方与可选依赖 |
| Windows/macOS 同步调用阻塞事件循环 | 桌面能力统一 `asyncio.to_thread`，并在两个平台各跑一次 e2e |
| setuptools 自动发现遗漏新包 | P0 验证 `pip install -e` 后能导入新骨架包 |
