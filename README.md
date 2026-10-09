# fm_agent_frame

从零手写的 **Agent 编排框架**，用于学习 AI Agent 的核心机制。

不依赖 LangChain / LangGraph，用 Python 3.12 + async，后端 LLM 走 DeepSeek（OpenAI 兼容协议）。目标是「总-分」式学习：先看清全景（有哪些模块、各自干什么、如何协作），再逐个模块深入。

## 架构全景

```
用户输入
   │
   ▼
┌──────────────┐    ┌──────────┐
│  agent       │───▶│  llm     │────▶ DeepSeek (OpenAI 兼容)
│  (ReAct 循环) │    │  (协议)   │
└──────┬───────┘    └──────────┘
       │ 调用工具
       ▼
┌──────────────┐    ┌──────────┐
│  tools       │    │  memory  │
│  (注册表)     │    │  (记忆)   │
└──────────────┘    └──────────┘
```

核心数据流（agent 循环）：

```
用户输入 → Agent.run
  → Memory.load 组装历史消息
  → LLMProvider.chat(messages, tools)          # async
  → 返回 Assistant 消息，含 tool_calls?
     ├─ 是 → 逐个执行 Tool → ToolMessage 回填 → 再调 LLM
     └─ 否 → 输出最终文本 → AgentResult
```

## 模块地图

| 模块 | 职责 | 状态 |
|---|---|---|
| `messages` | 消息模型（System/User/Assistant/Tool/ToolCall） | ✅ 实现 |
| `config` | 配置加载（pydantic-settings，API key 走 env） | ✅ 实现 |
| `errors` | 统一异常体系 | ✅ 实现 |
| `llm` | `LLMProvider` 协议 + `OpenAICompatProvider` 实现 | ✅ 实现 |
| `tools` | `Tool` 协议 + `ToolRegistry` + 内置工具 | ✅ 实现 |
| `agent` | `Agent` 协议 + `ToolUseAgent`（ReAct 循环） | ✅ 实现 |
| `memory` | 多层记忆接口（对话/画像/语义/情景）+ `ConversationMemory` | 🟡 接口全·极简实现 |
| `prompt` | 模板/多消息/版本库/示例选择接口 + `StringTemplatePrompt` | 🟡 接口全·极简实现 |
| `obs` | `Tracer` 协议 + `setup_logging` 双路日志 | 🟡 接口全·极简实现 |
| `retrieval` | RAG 流水线接口（Loader/Chunker/Embedder/VectorStore/Retriever/Reranker） | 🔵 接口全·零实现 |
| `multi_agent` | 编排接口（AgentSpec/SubTask/TaskDecomposer/Orchestrator） | 🔵 接口全·零实现 |
| `eval` | 评测接口（EvalCase/Evaluator/EvalSuite/EvalReport） | 🔵 接口全·零实现 |
| `server` | HTTP 服务接口（ChatRequest/AgentService/SessionManager） | 🔵 接口全·零实现 |

> ✅ 实现 / 🟡 接口完整 + 极简实现 / 🔵 接口完整、零实现
>
> 13 个模块的**接口均已定义完毕**：打开任意模块的 `base.py`，通过 Protocol 和 docstring 即可看清它对外提供的能力。主链路（`messages`/`llm`/`tools`/`agent`）已完整可跑，其余模块待逐个实现。

## 快速开始

```bash
# 1. 激活环境并安装
conda activate py312
pip install -e ".[dev]"

# 2. 配置 API key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-xxx

# 3. 跑首个演示：Agent 循环 + 工具调用
python examples/02_tool_agent.py

# 4. 交互式多轮对话（输入 exit 退出）
python examples/03_interactive.py
```

## 运行测试

```bash
pytest
```

（agent 循环的测试用 fake LLM，不依赖真实 API。）

## 调试日志

日志分两路输出（目录由 `LOG_DIR` 配置，默认 `log`）：

- **主日志**：控制台 + `log/agent.log`，记录框架运行日志（不含 LLM 交互）
- **LLM 交互日志**：`log/llm.log`，只记录与 LLM 的**请求**（messages + tools）和**回包**的原始 JSON

级别通过 `LOG_LEVEL` 环境变量（或 `.env`）配置，设成 `DEBUG` 会打印 LLM 请求/回包：

```bash
LOG_LEVEL=DEBUG python examples/02_tool_agent.py
```

## 学习路线

从「主线」学起：`messages → llm → tools → agent`，学完就能看懂 `examples/02_tool_agent.py` 的每一行。完整路线见 [docs/roadmap.md](docs/roadmap.md)。
