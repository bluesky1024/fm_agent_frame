# 学习路线图

按依赖方向逐层阅读：每层只依赖下一层，所以从 `core` 开始不会遇到「看不懂的调用」。

## 阶段一：内核（先跑通一条主线）

| 模块 | 先学什么 | 再看什么 |
|---|---|---|
| `core/messages` | 四种 role；assistant 的 tool_calls 与 tool 的 tool_call_id 如何配对 | 多模态内容分片 |
| `core/events` | 九类运行事件如何描述一次循环 | 为什么 Tracer/SSE/评测共用事件流 |
| `llm` | `chat()` 与 `stream()` 两条路径；内部扁平模型 ↔ 线上嵌套协议 | 流式 tool_call 分片拼接、用量提取、错误重试 |
| `tools` | 自包含 `ToolSpec`；JSON Schema 校验；并行、超时与错误分类 | 为什么工具层不能依赖 LLM 层 |
| `runtime` | `AgentRuntime.run(spec, session, input)` 的循环 | 中间件、护栏、审批、取消与步数上限 |

学完这一阶段，可以读懂 `examples/02_tool_agent.py` 的完整事件流。

## 阶段二：上下文与状态

| 模块 | 学什么 |
|---|---|
| `context` | 每轮请求视图如何装配；为什么装配结果不写回历史 |
| `memory` | 会话历史、摘要 + 滑动窗口；长期记忆协议 |
| `interfaces/session` | Session 与 SessionManager 的状态归属和多会话隔离 |

对应示例：`examples/03_interactive.py`。

## 阶段三：能力层

| 模块 | 学什么 |
|---|---|
| `obs` | 事件驱动的 Console/JSONL trace、token 与步骤耗时 |
| `capabilities/retrieval` | 确定性 embedder + 内存向量库 + 上下文提供者 |
| `capabilities/multi_agent` | 顺序编排；并行/交接协议 |
| `capabilities/guardrails` / `hitl` | 输入输出护栏、工具审批 |
| `capabilities/mcp` / `sandbox` | 外部工具与执行隔离协议 |
| `eval` | 精确/正则评测、批量报告 |
| `interfaces/server` | FastAPI 单端点 + SSE + 多会话 |

## 阶段四：计算机使用与应用

| 模块 | 学什么 |
|---|---|
| `capabilities/computer_use` | 截屏/鼠标后端协议、观察、标注；`asyncio.to_thread` 隔离同步调用 |
| `apps/minesweeper` | 应用如何用 `AgentSpec` 组合框架能力；fake LLM + fake 后端 e2e |

对应示例：`examples/04_minesweeper_autoplay.py`。

## 建议的阅读顺序

```text
core → llm → tools → runtime → context → memory
     → capabilities（按兴趣）→ interfaces → apps
```

每个模块先读公开协议与 docstring，再读实现；测试文件本身就是行为说明。
