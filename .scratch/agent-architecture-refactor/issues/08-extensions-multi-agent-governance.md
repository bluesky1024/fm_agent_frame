# 08: 扩展能力（多 Agent 编排与治理协议）

**What to build:** 使用者可以用顺序编排把任务拆给多个 agent，也可以通过护栏、审批、MCP 与沙箱协议扩展运行时；未实现的能力以空实现接入链路，默认行为不变。

**Blocked by:** 04, 06

**Status:** done

- [x] 顺序编排可将两个子任务交给运行时执行并汇总结果
- [x] 并行编排与 agent 交接仅保留协议
- [x] 输入与输出护栏可拦截请求/响应并产生明确事件
- [x] 审批策略提供自动批准与控制台审批，审批状态可查询
- [x] MCP 工具提供者与沙箱执行器仅有协议和 no-op 实现，但真实接入工具执行链路
- [x] 默认配置下运行时主流程行为与接线前一致
- [x] 测试全绿

## Comments

- 2026-10-17: 实现完成。`multi_agent` 迁入 capabilities 并提供 SequentialOrchestrator（并行/交接仅协议）；runtime 接入输入/输出护栏（`Error` 事件短路）与审批（拒绝时回填可恢复工具结果）；新增 AutoApprove/ConsoleApprove（记录可按 call_id 查询）、MCPToolProvider/NullMCPClient、NoopToolSandbox。默认无护栏/审批时行为不变。新增 9 个测试，全量 129 passed。
