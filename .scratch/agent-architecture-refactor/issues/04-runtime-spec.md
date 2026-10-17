# 04: AgentRuntime 与 AgentSpec

**What to build:** 使用者可以用无状态 spec 声明一个 agent，并通过唯一运行时执行它；运行过程以事件流输出，支持工具循环、步数上限、取消与中间件。

**Blocked by:** 03

**Status:** done

- [x] AgentSpec 以数据声明模型、提示词、工具、记忆、步数上限、中间件与扩展策略
- [x] 运行时返回事件流；另有收集接口返回结构化结果（最终文本、用量、步数）
- [x] 工具调用循环、步数上限、取消与中间件钩子均按预期工作
- [x] 最小上下文装配接入运行时，装配结果不写回持久历史
- [x] 用假 LLM 驱动的一次工具调用通过事件序列断言
- [x] 旧 agent 仍可运行，新运行时与旧路径并存且互不影响
- [x] 测试全绿，类型检查通过

## Comments

- 2026-10-17: 实现完成。新增 `AgentSpec`（冻结 dataclass）、`Session` 协议与 `InMemorySession`、`AgentRuntime.run/run_collect`、`context` 最小装配（system + provider 片段 + 历史），以及中间件/护栏/审批协议。流式增量即时转发；工具轮 assistant 文本与失败结果落历史；取消以 `Error + RunEnd` 收尾后继续抛出 `CancelledError`。运行时测试 9 个，全量 111 passed。
