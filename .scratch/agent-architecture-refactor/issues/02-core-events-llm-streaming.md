# 02: 核心模型、事件与 LLM 流式

**What to build:** 使用者可以通过新的 LLM 供应商接口发起整包或流式对话，并拿到带用量与错误映射的结果；全局共享的消息、错误、配置与事件类型从核心层统一导出。

**Blocked by:** 01

**Status:** done

- [x] 消息、错误与配置统一迁入核心层，其他模块只从核心层导入
- [x] 事件类型覆盖运行开始、步骤开始、上下文已装配、文本增量、LLM 完成、工具调用请求、工具结果、运行结束与错误
- [x] 供应商接口同时支持整包与流式调用，流式增量可拼装为完整消息
- [x] OpenAI 兼容实现支持流式、用量提取与可配置重试
- [x] 消息转换与流式组装通过伪 wire chunk 测试，不访问真实网络
- [x] 测试全绿，依赖检查通过

## Comments

- 2026-10-17: 实现完成。`core` 新增 events/types/images 并迁入 messages/errors/config；`LLMProvider` 增加 `stream()`，OpenAI 兼容实现支持文本增量、按 index 拼接 tool_calls 分片、用量提取与可重试错误映射。llm→obs 的违规依赖通过把图片落盘工具移到 `core.images` 消除，import-linter 忽略项只剩 tools→llm（票 03 移除）。新增事件与流式测试 14 个，全量 91 passed；mypy 已覆盖 llm 并保持 strict。
