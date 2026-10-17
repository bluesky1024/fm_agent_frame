# 05: 示例迁移与旧 Agent 移除

**What to build:** 三个教学示例改用新的运行时与 spec API；旧 agent 与 prompt 路径及其测试被彻底删除，仓库不再存在双轨入口。

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] 基础对话、工具调用、交互式多轮三个示例均使用新 API 并可运行
- [ ] 旧 agent 与 prompt 模块及其测试删除，不保留兼容层
- [ ] 全仓不再引用旧模块路径
- [ ] 示例中的事件输出与流式输出可见
- [ ] 测试全绿，依赖检查通过
