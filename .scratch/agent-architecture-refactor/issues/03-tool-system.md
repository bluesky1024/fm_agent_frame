# 03: 工具系统重构

**What to build:** 使用者可以注册自包含的工具定义，并在调用时获得参数校验、同批并行、超时与错误分类；工具层不再依赖 LLM 层。

**Blocked by:** 02

**Status:** done

- [x] 工具定义自包含，工具层不再 import 任何 LLM 模块
- [x] 参数不符合 schema 时返回结构化错误，且不执行工具
- [x] 同一批工具并行执行，单次调用有超时限制
- [x] 可恢复错误作为工具结果返回；致命错误向上抛出
- [x] 内置工具迁移后行为保持一致
- [x] 测试全绿，依赖检查通过

## Comments

- 2026-10-17: 实现完成。新增 `ToolExecutor`（JSON Schema 校验、`asyncio.gather` 并行、`wait_for` 超时、错误分类、ToolProvider/ToolSandbox 接线）与自包含 `ToolResult`；`ToolSpec` 改为 core 共享类型。新增 `jsonschema` 依赖，mypy 严格检查扩展到 tools，tools→llm 忽略项已从 import-linter 移除。工具测试 11 个，全量 102 passed。
