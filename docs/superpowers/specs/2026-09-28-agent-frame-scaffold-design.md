# Agent 框架学习项目脚手架设计

- 日期：2026-09-28
- 状态：已确认（待实现）
- 类型：新项目脚手架

## 1. 定位与目标

本项目是用于**学习 AI Agent 编排框架**的个人学习项目。核心诉求是"总-分"式学习：先看清 Agent 框架的全景（有哪些模块、各自干什么、如何协作），再逐个模块深入实现与理解。

关键决策：

| 决策项 | 结论 |
|---|---|
| 实现路线 | 从零手写，不依赖 LangChain/LangGraph |
| 主体语言 | Python 3.12（`conda activate py312`） |
| LLM 后端 | DeepSeek API（OpenAI 兼容协议，`https://api.deepseek.com`，模型 `deepseek-chat` / `deepseek-reasoner`） |
| LLM SDK | 官方 `openai` SDK（指向 DeepSeek base_url） |
| 并发模型 | async/await |
| 内部接口风格 | `typing.Protocol` + 完备类型标注 |
| 首期粒度 | 核心模块铺全、接口完备、部分模块打桩零实现 |
| 首个演示 | CLI 跑通 tool 调用（agent 循环 + 1~2 个工具 + DeepSeek） |
| 前台 | 预留，后续 Vue/React 均可 |

## 2. 模块地图

共 13 个模块，首期状态分三档：✅ 实现 / 🟡 部分实现 / 🔵 打桩（接口完备、零实现或抛 `NotImplementedError`）。

| 模块 | 职责 | 首期状态 |
|---|---|---|
| `messages` | 消息模型（System/User/Assistant/Tool/ToolCall） | ✅ |
| `config` | 配置加载（pydantic-settings，API key 走 env） | ✅ |
| `errors` | 统一异常体系 | ✅ |
| `llm` | `LLMProvider` 协议 + `OpenAICompatProvider` 实现 | ✅ |
| `tools` | `Tool` 协议 + `ToolRegistry` + 内置工具（计算器/取当前时间） | ✅ |
| `agent` | `Agent` 协议 + `ToolUseAgent`（ReAct 循环） | ✅ |
| `memory` | `Memory` 协议 + `ConversationMemory`（短时记忆）；向量记忆打桩 | 🟡 |
| `prompt` | `PromptTemplate` 协议 | 🟡 |
| `obs` | `Tracer` 协议 + 结构化日志 | 🟡 |
| `retrieval` | `Retriever` 协议（RAG） | 🔵 |
| `multi_agent` | 多 agent 编排协议 | 🔵 |
| `eval` | 评测协议 | 🔵 |
| `server` | FastAPI 服务（为 Vue/React 预留） | 🔵 |

## 3. 核心数据流（agent 循环）

```
用户输入 → Agent.run
  → Memory.load 组装历史消息
  → LLMProvider.chat(messages, tools)           # async
  → 返回 Assistant 消息，含 tool_calls?
     ├─ 是 → 逐个 tool_call：ToolRegistry 取 Tool → Tool.run(**args) → ToolMessage 回填 → 再调 LLM
     └─ 否 → 输出最终文本 → AgentResult
```

循环设最大步数（如 8 步）防止死循环。

## 4. 关键接口签名（Protocol）

```python
# llm/base.py
class LLMProvider(Protocol):
    async def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] | None = ...,
    ) -> AssistantMessage: ...

# tools/base.py
class Tool(Protocol):
    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict]              # JSON Schema
    async def run(self, **kwargs: Any) -> str: ...

# agent/base.py
class Agent(Protocol):
    async def run(self, task: str, *, memory: Memory | None = ...) -> AgentResult: ...
```

## 5. 错误处理

- 异常基类 `AgentFrameError` + 子类 `LLMError` / `ToolError` / `AgentLoopError` / `ConfigError`。
- LLM 调用带超时与有限重试（可配置）。
- Tool 执行异常**包装成 ToolMessage 反馈给 LLM**（让其自行修正），不中断循环。

## 6. 测试策略

- `pytest` + `pytest-asyncio`。
- 单元测试：消息序列化、`ToolRegistry`、内置工具。
- agent 循环用 fake `LLMProvider` 测试，不依赖真实 API。
- 真实 DeepSeek 调用放 `examples/` 手动运行。

## 7. 目录结构

```
fm_agent_frame/
├── README.md                # 定位、架构图、学习路线
├── pyproject.toml           # openai, pydantic, pydantic-settings, fastapi(预留)
├── .env.example             # DEEPSEEK_API_KEY 等
├── .gitignore
├── src/agent_frame/
│   ├── __init__.py
│   ├── config.py
│   ├── errors.py
│   ├── messages.py
│   ├── llm/
│   │   ├── base.py          # LLMProvider 协议 + 响应类型
│   │   └── openai_compat.py
│   ├── tools/
│   │   ├── base.py          # Tool 协议
│   │   ├── registry.py
│   │   └── builtin/         # calculator, time
│   ├── agent/
│   │   ├── base.py          # Agent 协议 + AgentResult
│   │   └── tool_use.py      # ToolUseAgent（ReAct）
│   ├── memory/
│   │   ├── base.py
│   │   └── conversation.py
│   ├── prompt/base.py
│   ├── retrieval/base.py
│   ├── multi_agent/base.py
│   ├── eval/base.py
│   ├── obs/tracer.py
│   └── server/app.py        # 预留
├── examples/
│   ├── 01_hello_llm.py
│   └── 02_tool_agent.py     # 首个演示
├── tests/
└── docs/
    └── roadmap.md           # 学习路线图
```

## 8. 依赖清单

- 运行时：`openai`、`pydantic`、`pydantic-settings`
- 预留：`fastapi`、`uvicorn`（server 模块打桩，可后续再装）
- 开发：`pytest`、`pytest-asyncio`
