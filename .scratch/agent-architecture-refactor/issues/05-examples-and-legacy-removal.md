# 05: 示例迁移与旧 Agent 移除

**What to build:** 三个教学示例改用新的运行时与 spec API；旧 agent 与 prompt 路径及其测试被彻底删除，仓库不再存在双轨入口。

**Blocked by:** 04

**Status:** done

- [x] 基础对话、工具调用、交互式多轮三个示例均使用新 API 并可运行
- [x] 旧 agent 与 prompt 模块及其测试删除，不保留兼容层
- [x] 全仓不再引用旧模块路径
- [x] 示例中的事件输出与流式输出可见
- [x] 测试全绿，依赖检查通过

## Comments

- 2026-10-17: 实现完成。示例 01–03 改用 `AgentSpec` + `AgentRuntime`，新增 `examples/_events.py` 统一打印事件与流式增量；删除 `agent/`、`prompt/` 及 `test_agent.py`、`test_observer_loop.py`。`desktop/minesweeper.py` 因示例 04 依赖，提前改为新运行时 + `ObserverContextProvider`（票 10 会迁入 apps）。新增示例可导入性测试，全量 108 passed。
