# 06: 请求视图与状态（上下文、记忆、会话、最小检索）

**What to build:** 每轮请求由上下文装配统一生成，历史由记忆持久化并在超阈值时压缩，会话承载多轮状态，最小检索能力作为上下文提供者接入；同时修复重复写入 system 与丢弃工具轮文本的缺陷。

**Blocked by:** 04

**Status:** done

- [x] 每轮请求包含 system、压缩后的历史、记忆召回与检索片段，且装配结果不写回持久历史
- [x] 工具轮中 assistant 的文本被完整保留；工具失败结果进入历史
- [x] 摘要加滑动窗口在超过阈值时触发，并能在下一轮请求中生效
- [x] Session 支持多轮对话与多会话隔离，状态归属明确
- [x] 内存检索流水线使用确定性 embedder，检索片段可作为上下文提供者注入
- [x] 长期记忆能力仅保留协议，不实现
- [x] 装配、压缩、会话隔离与检索注入测试通过

## Comments

- 2026-10-17: 实现完成。新增 `SummaryBufferMemory`（摘要 + 滑动窗口，`view` 不改写原始历史）与 `context.compaction`；`Session` 增加 `memory`，运行时每轮从记忆加载、逐条持久化并先压缩再装配。检索迁入 `capabilities/retrieval`（确定性 embedder + 内存向量库 + `RetrievalContextProvider`），删除旧顶层 `retrieval/`。测试覆盖装配顺序、压缩生效、多会话隔离与检索注入，全量 115 passed。
