# ADR-0005：分层依赖与依赖倒置

- 状态：已接受
- 日期：2026-10-17
- 决策者：仓库所有者 + Claude

## 背景

现状存在 `tools/base.py` 反向依赖 `llm/base.py`，以及 `desktop` 与 `tools/desktop` 之间的循环导入。模块边界没有机器约束，重构后容易再次腐化。

## 决策

依赖分层（上层依赖下层）：

```text
interfaces
capabilities
runtime
context
llm · tools · memory · obs
core
```

配套规则：

- `core` 不 import 任何内部包。
- `tools` 不 import `llm`。
- `capabilities` 不 import `interfaces`。
- 框架包不 import `apps` / `examples`。
- `runtime` 定义扩展协议（Middleware、Guardrail、ApprovalPolicy），由 `capabilities` 实现；`context` 定义 `ContextProvider`，由 `retrieval` 实现。
- 用 import-linter 在 `scripts/check.py` 中强制以上约束。

## 后果

正面：

- 依赖方向可被机器验证，避免循环导入与反向耦合回归。
- 能力层可插拔：替换检索、护栏、沙箱实现不影响运行时。

负面：

- 协议与实现分离带来额外间接层，初学者需要理解"谁定义接口、谁实现"。
- import-linter 契约需随目录调整维护。

## 替代方案

- **只在文档中约定依赖**：无强制力，未采用。
- **用独立发布包隔离**：学习项目过度设计，未采用。
