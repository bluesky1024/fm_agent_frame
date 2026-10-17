# 01: 基线与本地检查工具链

**What to build:** 建立新分层包骨架与本地质量检查，让后续重构每一步都能被 lint、类型、依赖规则与测试验证，同时不改变现有行为。

**Blocked by:** None（可立即开始）

**Status:** ready-for-agent

- [ ] 新分层包骨架可正常导入，旧代码保持原位且行为不变
- [ ] dev 依赖包含 lint/format、类型检查、依赖检查工具，可通过 pip 安装
- [ ] 提供一条跨平台检查命令，依次运行 lint、format、类型检查、依赖检查与测试
- [ ] 依赖检查契约覆盖分层方向与三条禁止规则：tools 不得依赖 llm、core 不得依赖内部模块、capabilities 不得依赖 interfaces
- [ ] 现有测试保持全绿（基线 74 个用例）
