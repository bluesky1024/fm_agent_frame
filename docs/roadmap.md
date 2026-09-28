# 学习路线图

建议按依赖顺序逐模块学习：先看懂「一条主线」（LLM → Agent 循环 → Tool），再补全周边模块。

## 阶段一：主线（先跑通）

| 模块 | 先学什么 | 再看什么 |
|---|---|---|
| `messages` | 消息有哪几种 role，tool_call 如何关联 tool 消息 | 为什么 assistant 的 tool_calls 和 tool 的 tool_call_id 成对出现 |
| `llm` | `LLMProvider` 协议；OpenAI 兼容协议的长相；内部扁平模型 ↔ 线上嵌套协议的转换 | 流式输出、多模型切换、重试策略 |
| `tools` | `Tool` 协议三要素（name/description/parameters）；JSON Schema 怎么告诉 LLM 参数 | 为什么 calculator 用 ast 白名单而不是 eval |
| `agent` | ReAct 循环：思考 → 调工具 → 观察 → 再思考；最大步数为何要设上限 | 为什么工具异常要回填给 LLM 而不是中断 |

学完这四块，`examples/02_tool_agent.py` 的每一行就都能看懂了。

## 阶段二：周边（按兴趣选）

| 模块 | 学什么 |
|---|---|
| `memory` | 短时记忆怎么组织；长时记忆 / 向量记忆怎么做（当前打桩） |
| `prompt` | 提示词模板化、系统提示词工程 |
| `config` | pydantic-settings 如何从 env/.env 读配置 |
| `errors` | 为什么要统一异常体系、怎么分层捕获 |
| `obs` | 结构化日志、调用链追踪、token 用量 |

## 阶段三：进阶（当前打桩）

| 模块 | 学什么 |
|---|---|
| `retrieval` | RAG：向量化、检索、如何把外部知识喂给 LLM |
| `multi_agent` | 多 Agent 协作：任务拆分、编排、汇总 |
| `eval` | 如何衡量 Agent 输出质量 |
| `server` | 用 FastAPI 暴露 HTTP 接口，接 Vue/React 前台 |
