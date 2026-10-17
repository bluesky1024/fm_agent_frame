# 01: 基线与本地检查工具链

**What to build:** 建立新分层包骨架与本地质量检查，让后续重构每一步都能被 lint、类型、依赖规则与测试验证，同时不改变现有行为。

**Blocked by:** None（可立即开始）

**Status:** done

- [x] 新分层包骨架可正常导入，旧代码保持原位且行为不变
- [x] dev 依赖包含 lint/format、类型检查、依赖检查工具，可通过 pip 安装
- [x] 提供一条跨平台检查命令，依次运行 lint、format、类型检查、依赖检查与测试
- [x] 依赖检查契约覆盖分层方向与三条禁止规则：tools 不得依赖 llm、core 不得依赖内部模块、capabilities 不得依赖 interfaces
- [x] 现有测试保持全绿（基线 78 个用例；同时修复 Windows 下路径断言导致的既有失败）

## Comments

- 2026-10-17: 实现完成，`python scripts/check.py` 全绿（78 passed，5 条依赖契约全部通过）。两处遗留违规（tools → llm）以显式 ignore 登记，票 03 移除。`ruff format` 对既有 Python 文件做了基线格式化；`docs/` 与 `games/` 排除在自动格式化之外。
