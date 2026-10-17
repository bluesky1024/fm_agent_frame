# ADR-0007：首版实现深度与本地工具链

- 状态：已接受
- 日期：2026-10-17
- 决策者：仓库所有者 + Claude

## 背景

目标架构包含较多模块。若全部完整实现，重构周期过长；若全部只留接口，又无法满足"流程完备"。同时需要决定静态检查与 CI 方案。

## 决策

实现深度：

- **完整**：`core`、`llm`、`tools`、`runtime`、`context`、`interfaces/session`、`computer_use`、`apps/minesweeper`。
- **最小闭环**：`obs`、`retrieval`、`eval`、`multi_agent`（顺序编排）、`interfaces/cli`、`interfaces/server`、`memory` 的摘要压缩。
- **接口 + 空实现（真实接线）**：`guardrails`、`mcp`、`sandbox`；`hitl` 提供自动批准与控制台审批；长期记忆仅协议。
- 检索使用内存向量库与确定性假 embedder，不引入外部服务。

工具链：

- 本地引入 `ruff`（lint + format）、`mypy`（P0 起 `core`/`runtime` 严格，`llm`/`tools` 随票 02/03 纳入）、`import-linter`（依赖规则）。
- 统一由 `scripts/check.py` 执行，Windows 与 macOS 命令一致。
- **暂不启用 GitHub Actions**；后续需要时复用同一组命令即可。
- 真实 API 人工验收安排在"基本完备版本"达成后，不作为每阶段门槛。

## 后果

正面：

- 重构范围可控，每个模块都有可运行或可接线的最小形态。
- 本地工具链零系统依赖，两个平台均可使用。
- 避免在重构早期被 CI 配置与真实 API 波动阻塞。

负面：

- 没有 CI 意味着检查依赖自觉执行；需要在文档与脚本中保持显眼。
- 最小实现距离生产可用仍有差距，需要后续迭代。

## 替代方案

- **全部完整实现**：周期不可控，未采用。
- **全部只留接口**：流程无法闭环，未采用。
- **引入 GitHub Actions**：当前暂不需要，保留为后续可选项。
