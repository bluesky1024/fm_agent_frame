# 09: 最小 HTTP 服务与多会话

**What to build:** 使用者可以通过一个 HTTP 端点发起对话并流式接收事件，服务端隔离多个会话。

**Blocked by:** 06

**Status:** done

- [x] 单个聊天端点接受输入并流式返回运行事件
- [x] SessionManager 管理多个会话，会话之间状态互不干扰
- [x] 非法输入返回结构化错误
- [x] 服务层测试通过，另有一个 HTTP/SSE 冒烟测试
- [x] 未引入认证、多租户或分布式能力

## Comments

- 2026-10-17: 实现完成。新增 `interfaces/server`（ChatRequest/ChatResponse、AgentService、`POST /chat` 的 SSE 与非流式分支、422 结构化错误）与 `SessionManager`；删除旧顶层 `server/`。依赖新增 fastapi/uvicorn（server extra）与 httpx（dev）。测试 8 个，全量 137 passed。
