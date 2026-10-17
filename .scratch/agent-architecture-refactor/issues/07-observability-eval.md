# 07: 可观测与评测

**What to build:** 运行过程可以被追踪并量化，使用者能对一组用例跑批并得到结构化报告；追踪与评测都消费同一事件流。

**Blocked by:** 04

**Status:** done

- [x] Tracer 消费运行时事件，支持控制台与 JSONL 输出
- [x] token 用量与步骤耗时按运行和步骤统计
- [x] 精确匹配与正则匹配评测器可用
- [x] 评测套件可对假 LLM 跑批并输出结构化报告
- [x] trace 文件在运行后生成且内容可读
- [x] 测试全绿

## Comments

- 2026-10-17: 实现完成。`Tracer` 改为事件消费者并提供 ConsoleTracer/JSONLTracer，运行时统一分发事件并在结束时关闭；新增 `TokenTracker`（按 run/step 统计 token、耗时、工具调用数）。评测新增 ExactMatch/RegexMatch 与 `AgentEvalSuite`（消费 runtime 事件流、session_factory 注入）。示例 02 接入 JSONLTracer 生成 `log/trace.jsonl`。测试 5 个，全量 120 passed（当时）。
