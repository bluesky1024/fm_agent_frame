# 01: 基线与本地检查工具链

**What to build:** 建立新分层包骨架与本地质量检查，让后续重构每一步都能被 lint、类型、依赖规则与测试验证，同时不改变现有行为。

**Blocked by:** None（可立即开始）

**Status:** done

- [x] 新分层包骨架可正常导入，旧代码保持原位且行为不变
- [x] dev 依赖包含 lint/format、类型检查、依赖检查工具，可通过 pip 安装
- [x] 提供一条跨平台检查命令，依次运行 lint、format、类型检查、依赖检查与测试
- [x] 依赖检查契约覆盖分层方向与三条禁止规则：tools 不得依赖 llm、core 不得依赖内部模块、capabilities 不得依赖 interfaces
- [x] 既有 65 个用例在修复 Windows 路径断言后全绿；本票新增 13 个骨架用例，共 78 个

## Comments

- 2026-10-17: 实现完成，`python scripts/check.py` 全绿（既有 65 + 新增 13 = 78 passed，5 条依赖契约全部通过）。两处遗留违规（tools → llm）以显式 ignore 登记，票 03 移除。`ruff format` 对既有 Python 文件做了基线格式化；`docs/` 与 `games/` 排除在自动格式化之外。
- 2026-10-17: 双轴评审后修正：恢复 obs 在 L1 的分层，不再为迁就实现改动架构；eval 纳入 layers 契约；基线口径改为“既有 65 + 新增 13”；文档化 `Status: done` 约定。mypy 仍按计划在票 02/03 扩展到 llm/tools；tools→llm 的两处 ignore 保留至票 03。
