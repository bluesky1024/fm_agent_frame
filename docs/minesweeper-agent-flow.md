# 扫雷视觉 Agent 调用流程

> 梳理 `examples/04_minesweeper_autoplay.py` 从启动到结束的完整调用脉络。
> 每条链路都对应仓库里的实际源码。

## 1. 组件全景（谁调用谁）

```mermaid
flowchart TD
    EX["examples/04_minesweeper_autoplay.py<br/>启动游戏 + 组装 + run_autoplay"]
    EX -->|launch_game| GAME["games/minesweeper.py<br/>无边框、置顶的 tkinter 扫雷"]
    EX -->|MinesweeperConfig.from_board_config| CFG["apps/minesweeper/config.py"]
    EX -->|run_autoplay| APP["apps/minesweeper/agent.py<br/>build_agent"]
    APP -->|AgentSpec| RT["runtime.AgentRuntime<br/>唯一循环引擎"]
    RT -->|ContextBuilder| CTX["context<br/>system + 历史 + 观察帧"]
    CTX -->|ObserverContextProvider| OBS["BoardObserver<br/>ScreenObserver + GridAnnotator"]
    OBS -->|to_thread| CAP["ScreenCapture<br/>ScreenBackend（mss / fake）"]
    CAP -.截屏.-> GAME
    RT -->|stream| LLM["llm.OpenAICompatProvider"]
    RT -->|ToolExecutor| TOOLS["apps/minesweeper/tools<br/>click_cell / flag_cell"]
    TOOLS -->|to_thread| MOUSE["MouseController<br/>MouseBackend（pyautogui / fake）"]
    MOUSE -.真实鼠标点击.-> GAME
    LLM --> API["DeepSeek"]
```

纯文本版：

```text
examples/04_minesweeper_autoplay.py
  ① enable_dpi_awareness()
  ② config = MinesweeperConfig.from_board_config(board_config())
  ③ proc = launch_game()                     # 子进程启动目标扫雷
  ④ result = await run_autoplay(config, llm)
       └─ build_agent(config, llm)
            ├─ BoardObserver(capture, geometry)
            ├─ ToolRegistry(click_cell, flag_cell)
            ├─ AgentSpec(system_prompt, tools, context_providers=[ObserverContextProvider])
            └─ AgentRuntime + InMemorySession
```

## 2. 主循环（`AgentRuntime.run`）

```mermaid
flowchart TD
    INIT["session.memory.load<br/>append User(任务)"] --> STEP
    STEP["StepStart"] --> COMPACT["必要时 compact：摘要 + 滑动窗口"]
    COMPACT --> BUILD["ContextBuilder.build<br/>system + 历史 + 观察帧（末尾）"]
    BUILD --> GUARD["输入护栏（仅首步）"]
    GUARD --> STREAM["llm.stream(messages, tool_specs)"]
    STREAM --> DELTA["LLMDelta* → LLMCompleted"]
    DELTA --> HAS{有 tool_calls ?}
    HAS -- 是 --> APPROVE["审批 → ToolExecutor<br/>校验/并行/超时"]
    APPROVE --> TOOLMSG["ToolResult 事件 + 写入历史"]
    TOOLMSG --> STEP
    HAS -- 否 --> OUT["输出护栏 → RunEnd(result, usage)"]
    OUT --> CHECK{应用层读图判定胜负}
    CHECK -- 已结束 --> DONE["退出"]
    CHECK -- 未结束 --> NUDGE["追加带计数的提示续跑（≤3 次）"]
    NUDGE --> STEP
    STEP -. 跑满 max_steps .-> ERR["Error + RunEnd"]
```

关键点：

- **观察帧不进历史**：`ObserverContextProvider` 在每轮装配时取一帧最新截图，
  并声明 `placement = "after_history"` 追加在历史之后；历史里只保留文本进展，
  模型看到的最后一条消息始终是当前画面。
- **装配结果不落盘**：system prompt、观察帧、检索片段只存在于本次请求视图。
- **工具轮文本保留**：assistant 的 `content` 与 `tool_calls` 一起写入历史。
- **工具失败也落历史**：可恢复错误以 tool 消息回填，模型下一轮能看到真实结果。
- **胜负以截图为准**：模型只能调用工具或输出固定结束结论，但应用层不直接相信文本；
  每次运行结束后读最新截图统计格子状态，只有真正结束才退出，否则追加带计数的提示续跑（≤3 次）。
- **鼠标串行**：同一批工具调用会并行分发，`MouseController` 用锁保证 Shift+点击与普通点击不交错。
- **点击前核对**：`click_cell` 读最近一帧，已翻开/已插旗的格子返回可恢复错误；点击丢失后仍可重试。

## 3. 一轮的时序

```mermaid
sequenceDiagram
    participant EX as 示例脚本
    participant RT as AgentRuntime
    participant CTX as ContextBuilder
    participant OB as BoardObserver
    participant LLM as LLM Provider
    participant TL as ToolExecutor
    participant GM as 扫雷游戏

    EX->>GM: launch_game()（子进程）
    EX->>RT: run(spec, session, "赢下这局扫雷。")
    loop 每步（≤ max_steps）
        RT->>CTX: build(system, history, input)
        CTX->>OB: observe()（Provider）
        OB->>GM: 截屏（to_thread）
        OB-->>CTX: 带标注的带图消息
        CTX-->>RT: 请求视图
        RT->>LLM: stream(视图, tools)
        LLM-->>RT: LLMDelta / LLMCompleted
        alt 有 tool_calls
            RT->>TL: execute_many(calls)
            TL->>GM: 真实鼠标操作（to_thread）
            TL-->>RT: ToolResult → 写入历史
        else 纯文本
            RT-->>EX: RunEnd(AgentResult)
            EX->>GM: 截屏并读取棋盘计数
            EX->>EX: 已结束？退出；否则追加带计数的提示续跑（≤3 次）
        end
    end
```

## 4. 两条子链路：看 / 做

```text
【看】BoardObserver.observe() → ScreenObserver
  await asyncio.to_thread(ScreenCapture.grab)
      │ · ScreenBackend 抓取 region（默认 mss，测试注入 fake）
      │ · scale = 物理像素 / 逻辑点，首次探测并缓存
      │ · 原始帧存入 last_image，供点击前核对与胜负校验
      ▼  PIL.Image（与鼠标坐标系 1:1）
  analyze_board() → 已翻开/未翻开/插旗计数写进 caption
  await asyncio.to_thread(GridAnnotator.draw)
      │ · 红色网格线 + 蓝色 1 基行列号
      ▼
  to_thread(下采样 + PNG 编码) → Message.user_with_image
      ▼
  交给 ContextBuilder，只进入本次请求视图

【做】ToolExecutor.execute_many
  click_cell(row,col) → BoardProbe 核对最近一帧（已翻开/已插旗则报错）
                      → cell_center → to_thread(MouseController.click)
  flag_cell(row,col)  → cell_center → to_thread(MouseController.shift_click)
      ▼
  MouseController 内部加锁，Shift+点击与普通点击不会交错
      ▼
  MouseBackend（默认 pyautogui，测试注入 fake）发事件 → 扫雷窗口响应
      ▼
  返回 "ok"；模型通过下一帧截图判断结果
```

## 5. 一次 LLM 请求的组装与落盘

```text
请求视图（不写回历史）：
  [System(扫雷提示词)]
  + [压缩后的历史：assistant/tool 文本]
  + [User(带网格的截图)]        ← ObserverContextProvider，每轮最新一帧
                                  placement="after_history"，始终位于末尾

         tools = 2 个工具的 JSON Schema
                         │
                         ▼
              openai_compat.stream()
                         │
        ┌────────────────┼──────────────────────────┐
        ▼                                           ▼
写 log/llm.log（始终 DEBUG）                  POST /chat/completions
 · 请求 messages + tools 的 JSON                · 图片以 base64 data URL 内联
 · 内联图片抽出落盘 log/pic/*.png（同图去重）
                         │
                         ▼
              LLMDelta → LLMCompleted(ChatResult)
```

若 spec 配置了 `JSONLTracer`，所有运行事件还会写入 `log/trace.jsonl`。

## 6. 关键设计点

| 点 | 说明 |
|---|---|
| **框架与应用分离** | 截屏/鼠标/观察/标注在 `capabilities/computer_use`；棋盘几何、工具、提示词、启动在 `apps/minesweeper` |
| **观察帧不进历史** | 由 ContextProvider 每轮贡献一帧，追加在历史之后，历史只留文本 |
| **胜负以截图为准** | `run_autoplay` 读图统计已翻开/未翻开/踩雷，模型结论不直接决定退出 |
| **纯文本兜底** | 未结束的响应追加带棋盘计数的提示续跑，最多 3 次 |
| **点击前核对** | `click_cell` 读最近一帧，已翻开/已插旗返回可恢复错误；点击丢失后可重试 |
| **鼠标串行** | `MouseController` 加锁，避免并行工具批次中 Shift 与点击交错 |
| **工具返回 `ok`** | 不回报坐标细节，让模型依据最新截图判断结果 |
| **插旗用 Shift+左键** | macOS 上 tkinter 收不到合成右键事件，只有左键能触发 |
| **坐标精确** | 1 基行列号 → `origin + (n-1)*cell + cell//2`；scale 归一化保证截图与鼠标坐标 1:1 |
| **不阻塞事件循环** | 截屏、标注、PNG 编码与鼠标操作都经 `asyncio.to_thread` |
| **e2e 可离线** | fake LLM + fake ScreenBackend/MouseBackend 覆盖观察、操作与结束 |

## 7. 对应源码

| 环节 | 文件 |
|---|---|
| 入口 / 启动 | `examples/04_minesweeper_autoplay.py`、`apps/minesweeper/launcher.py` |
| 目标游戏 | `games/minesweeper.py` |
| 主循环 | `src/agent_frame/runtime/runtime.py` |
| 请求装配 | `src/agent_frame/context/builder.py` |
| 应用组装 / 提示词 | `apps/minesweeper/agent.py`、`apps/minesweeper/prompt.py` |
| 结束结论 | `apps/minesweeper/outcome.py` |
| 配置 | `apps/minesweeper/config.py` |
| 观察者 | `apps/minesweeper/observer.py` |
| 截屏 / 鼠标 / 标注 | `src/agent_frame/capabilities/computer_use/{screen,mouse,annotate,observer}.py` |
| 坐标换算 | `apps/minesweeper/board.py` |
| 棋盘状态识别 | `apps/minesweeper/board_state.py` |
| 扫雷工具 | `apps/minesweeper/tools.py` |
| LLM 协议 / 日志 | `src/agent_frame/llm/openai_compat.py` |
| 图片落盘 | `src/agent_frame/core/images.py` |
| 事件 trace | `src/agent_frame/obs/tracer.py` |
