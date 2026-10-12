# 扫雷视觉 Agent 设计

- 日期：2026-10-11
- 状态：已确认（待实现）
- 类型：框架能力扩展 + 首个真实应用
- 前置：[Agent 框架学习项目脚手架设计](2026-09-28-agent-frame-scaffold-design.md)

## 1. 目标与定位

在现有 `fm_agent_frame` 学习框架上，新增一个能**在 Windows 上查看扫雷界面并控制鼠标全自动对局**的 Agent。它是框架从"纯文本 ReAct"迈向"**多模态计算机使用（computer-use）**"的第一个真实应用，也是新引入的"感知"能力维度的验证场景。

关键决策：

| 决策项 | 结论 |
|---|---|
| 技术路线 | 图片**直接喂给**多模态 LLM，模型原生看图决策（路线 A） |
| 视觉模型 | DeepSeek `deepseek-flash`（2026-09-10 GA，原生多模态，OpenAI 兼容 `image_url`） |
| 任务边界 | 一次 run **全自动对局**：看→做→再看循环，直到 `max_steps`；赢/踩雷后模型自行重开 |
| 目标程序 | 自写/第三方**简单版扫雷**（格子规整、无广告），几何由配置给出 |
| 坐标落地 | 截图上**叠加行列标注**，模型输出 `(row, col)`，工具换算成屏幕像素 |
| 感知载体 | 框架级 `Observer` 扩展点，每次动作后注入一帧最新截图 |
| 并发模型 | 沿用 async/await |
| 接口风格 | 沿用 `typing.Protocol` + 完备类型标注 |

### 已确认的取舍与已知风险

- 路线 A 最忠实于"让模型看图"的意图，也是学习价值最高的形态；代价是要改核心框架（多模态消息）。
- **纯视觉 LLM 稳定性有限**：初级以上难度会看错/算错，输多赢少。这与框架设计无关，是模型能力上限。若日后要求"必须赢"，需引入确定性求解器混合体（本设计不做，作为未来选项）。
- 路线 B（视觉封装进 `read_board` 工具、外层文本 ReAct）作为备选记录在 §9，不在本期实现范围。感知发生在框架层（Observer）而非工具内，是本期明确的选择。

## 2. 现有架构要点（改动基线）

- `Tool` 协议：类变量 `name`/`description`/`parameters`(JSON Schema) + `async def run(**args) -> str`；**工具统一返回文本**。
- `ToolUseAgent`：ReAct 循环 `chat → 执行工具 → 回填 tool 消息 → 再 chat`；工具异常包装成文本回填给 LLM。
- `Message.content: str | None`；`llm/openai_compat._to_openai_messages` 只透传字符串。
- LLM 后端默认 `deepseek-chat`（纯文本），配置见 `config.Settings`。

## 3. 总体架构与运行回路

新增 **`Observer`（观察者）** 作为框架级扩展点，把"感知"提升为一等公民：每轮动作之后注入一帧最新截图，模型永远基于最新棋盘决策。对纯文本 agent 零影响（默认 `None`）。

```
MinesweeperAgent.run("赢下这局扫雷")
  │
  ├─ messages = [system_prompt(扫雷专家), user(任务)]   # 永久历史：只有文本
  ├─ frame = observer.observe()                        # 当前帧：截图+标注 → 带图 user 消息
  │
  └─ for step in range(max_steps):
       payload = messages + [frame]                     # ★ 请求 = 完整文本历史 + 一帧最新截图
       result = llm.chat(payload, tools)                # deepseek-flash 原生看图
       ├─ 有 tool_calls:
       │    append assistant(tool_calls)
       │    for tc: 执行工具（click_cell/flag_cell/restart_game → 真操作鼠标）
       │             append tool(result)                # 工具结果精简为 "ok"
       │    frame = observer.observe()                  # ★ 替换当前帧，不 append 进历史
       │    continue
       └─ 纯文本: 记录并继续（游戏场景下模型基本一直走 tool_calls）
```

**观察帧不进历史**：`frame` 作为「当前帧」随每次请求临时附加，不进永久 `messages`。
否则历史里会堆满旧截图、每轮被重新发送（请求体随轮数膨胀）。发给 LLM 的永远是
「完整文本历史 + 一帧最新截图」。历史里的文本进展（assistant 的 tool_calls、tool 结果）照常保留。

`Observer` 协议（`agent/base.py`）：

```python
class Observer(Protocol):
    async def observe(self) -> Message: ...   # 返回一条（通常带图的）user 消息
```

- 一次 run = 一个自动游戏会话（可含多局）：模型赢了/踩雷后自己调 `restart_game` 重开，继续下一局；run 到 `max_steps` 结束。
- 重开次数可在示例层用 `--games N` 截断（示例读取 `AgentStep.tool_calls` 统计 `restart_game`）。
- 扫雷实现 `BoardObserver`：内部「截屏 → 叠加行列网格线 → 组装 `Message.user_with_image(text, png)`」。

## 4. 框架改动

### 4.1 `messages.py` — content 支持内容片段

```python
class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ImagePart(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: dict[str, str]          # {"url": data URL, "detail": "high"}

ContentPart = TextPart | ImagePart

class Message(BaseModel):
    ...
    content: str | list[ContentPart] | None = None

    @classmethod
    def user_with_image(cls, text: str, png: bytes, *, detail: str = "high") -> "Message":
        data_url = "data:image/png;base64," + base64.b64encode(png).decode()
        return cls(role="user", content=[
            TextPart(text=text),
            ImagePart(image_url={"url": data_url, "detail": detail}),
        ])
```

- 用 **base64 data URL** 内联传图（三选一：data URL / 外部 URL / Files API，选 data URL 以不依赖外部文件服务）。
- `str` 路径完全向后兼容。

### 4.2 `llm/openai_compat.py` — 透传内容片段

`_to_openai_messages` 增加分支：`content` 是 `list` 时逐片段 `model_dump()`，否则维持字符串透传。改动很小。

### 4.3 `agent/base.py` + `agent/tool_use.py` — 接入 Observer 钩子

- `agent/base.py`：新增 `Observer` 协议。
- `agent/tool_use.py`：构造函数新增 `observer: Observer | None = None`；`run` 中在**首轮前**与**每批工具执行后**各调用 `await observer.observe()`，结果存入 `frame` 并在每次请求时临时附加（**不 append 进历史**）。

### 4.4 需要留意的实现细节

- **图片分辨率**：DeepSeek 会把大图缩到约 1300×1300、单图约 ≤1024 token。截屏前**主动把标注图缩放到合理尺寸**（网格线清晰、数字可辨），省 token 又提速——进配置。
- **`detail` 参数**：读小数字需要精度，默认 `high`（或 `original`），可配。
- **影响面**：`Message.content` 类型变宽，需回归 `tests/test_messages.py` 与 memory 序列化；`ChatResult.content` 不变。

## 5. `desktop` 模块

新增包 `src/agent_frame/desktop/`：

| 文件 | 职责 | 关键接口 |
|---|---|---|
| `geometry.py` | 棋盘几何 ↔ 屏幕坐标换算 | `BoardGeometry(origin_x, origin_y, cell_w, cell_h, rows, cols)`；`cell_center(r, c) -> (x, y)` |
| `screen.py` | 截屏 | `ScreenCapture(region).grab() -> PIL.Image`（`mss`） |
| `mouse.py` | 鼠标控制 | `MouseController.click(x, y, button="left")`、`move_to`（`pyautogui`） |
| `annotate.py` | 叠加网格线 + 行列标尺 | `GridAnnotator(geometry).draw(img) -> PIL.Image` |
| `observer.py` | 串起"截屏→标注→组消息" | `BoardObserver`（实现 `Observer` 协议） |

坐标模型：

- `cell_center(r, c) = (origin_x + c * cell_w + cell_w/2, origin_y + r * cell_h + cell_h/2)`。
- 行列号约定：在棋盘**左侧标行号、顶部标列号**（1 基，模型直接读数字回传），工具内部换算（`r-1`/`c-1`）。
- 坐标为**屏幕绝对物理像素**。

## 6. 工具集

新增 `src/agent_frame/tools/desktop/`，三个工具通过构造器注入 `BoardGeometry` + `MouseController`（不同于无状态 builtin 工具）：

| 工具 | 参数 | 行为 | 返回 |
|---|---|---|---|
| `click_cell` | `row`, `col` | 左键点格心（翻开） | `ok` |
| `flag_cell` | `row`, `col` | Shift+左键点格心（插旗） | `ok` |
| `restart_game` | 无 | 按配置点重开按钮 / 发按键；模型判定"这局结束"时调用 | `ok` |

工具的 `name`/`description`/`parameters` 仍用类变量（满足 `Tool` 协议），依赖走实例构造器。

- **工具返回精简为 `ok`**：不回报"翻了哪格 / 点了哪个坐标"。模型应依据**最新截图**判断结果，而不是读工具回报文本；这也避免了每轮大量工具结果撑大请求体。
- **插旗用 Shift+左键**而非右键：macOS 上通过 pyautogui 合成的事件里，只有左键能被 tkinter 接收（实测右键/中键完全不触发事件）。`MouseController.shift_click` 负责按住 Shift 点击并保证释放。

## 7. 系统提示词（扫雷专家人设）

要点：

- 说明"每轮你会收到一张最新棋盘截图，格子已带行列标尺"。
- 工具用法（`click_cell` / `flag_cell` / `restart_game`）与行列号约定。
- **一轮做满**：把当前所有能确定的动作一次性做完（确定的雷全部 `flag_cell`、确定安全的格子全部 `click_cell`），不要一轮只做一个动作，也不要留到下一轮。
- 基本策略：数字 = 周围雷数；数字等于未开邻居数 → 全插旗；数字等于已插旗数 → 翻开其余；无法确定时挑**最可能安全**的格。
- 只依据最新截图决策，不重复操作已翻开的格子。
- **不输出推理/解释/思考过程**，直接调用工具（省 token、少一轮等待）。
- 棋盘完成（胜利或踩雷）时调 `restart_game`。

## 7. 系统提示词（扫雷专家人设）

要点：

- 说明"每轮你会收到一张最新棋盘截图，格子已带行列标尺"。
- 工具用法（`click_cell` / `flag_cell` / `restart_game`）与行列号约定。
- 基本策略：数字 = 周围雷数；数字等于未开邻居数 → 全插旗；数字等于已插旗数 → 翻开其余；无法确定时猜**最可能安全**的格。
- 一次可批量输出多个确定的动作以省 token。
- 棋盘完成（胜利或踩雷）时调 `restart_game`。

## 8. 配置、依赖与目录

### 8.1 依赖

`pyproject.toml` 新增可选组：

```toml
[project.optional-dependencies]
desktop = ["pyautogui", "pillow", "mss"]
```

### 8.2 配置

项目只保留自研目标程序（`games/minesweeper.py`），几何由 `board_config()` 自报、**免校准**；
不再有 `config/minesweeper.json`。`build_agent(config, llm)` 接收一个平铺的 config dict
（`geometry`/`region`/`restart`/`image_detail`/`image_max_px`/`max_steps`），由示例运行时构造。

- `restart` 支持 `{"type": "click", "x", "y"}` 或 `{"type": "key", "key": "f2"}`。
- **跨平台坐标缩放**（mss 像素 ↔ pyautogui 逻辑点归一化）详见 [跨平台适配设计](2026-10-12-minesweeper-cross-platform-design.md)。
- 全局 `Settings.model` 默认仍为 `deepseek-chat`；运行扫雷时用 `MODEL=deepseek-flash`（或配置文件指定）。
- **目标程序**：`games/minesweeper.py` 提供免校准的 tkinter 扫雷（固定窗口、无边框、置顶；几何由 `board_config()` 自报），`examples/04_minesweeper_autoplay.py` 自动启动它并对局。
- **接入外部扫雷**（可选）：量出「棋盘左上角格子外沿的屏幕坐标、单格宽高、截屏区域」，自行构造同结构的 config dict 调 `build_agent`。

### 8.3 目录结构（新增/改动）

```
src/agent_frame/
  messages.py                    # 改：多模态 content
  llm/openai_compat.py           # 改：多模态透传
  agent/base.py                  # 改：+ Observer 协议
  agent/tool_use.py              # 改：+ observer 钩子（当前帧不进历史）
  obs/llm_images.py              # 新：请求内联图片落盘 log/pic，日志只留引用
  desktop/                       # 新
    __init__.py  geometry.py  screen.py  mouse.py  annotate.py  observer.py  minesweeper.py
  tools/desktop/                 # 新
    __init__.py  click_cell.py  flag_cell.py  restart_game.py
games/minesweeper.py             # 新：免校准的自研 tkinter 扫雷（目标程序）
examples/04_minesweeper_autoplay.py  # 新：自动启动 games/minesweeper.py 并对局
tests/test_multimodal_messages.py
tests/test_desktop_geometry.py
tests/test_desktop_tools.py
tests/test_observer_loop.py
tests/test_minesweeper_game.py
docs/superpowers/specs/2026-10-11-minesweeper-vision-agent-design.md
```

## 9. 备选路线（本期不实现，仅记录）

**路线 B —— 视觉工具 + 文本决策**：新增 `read_board` 工具，内部「截图→标注→调视觉模型→返回结构化文本棋盘（每行：数字/未翻开/旗子）」，外层文本 `ToolUseAgent` 读文本棋盘决策再调 `click_cell`。

- ✅ 几乎不改核心框架（`Tool` 仍返回文本）；视觉封装成"传感器工具"，易测试；结构化文本更利于推理，更稳。
- ⚠️ 每步两次 LLM 调用；"看图"藏在工具内，"计算机使用"味道淡。
- 可作为 A 的调试/兜底，或未来 A 表现不佳时的替代。

## 10. 测试策略

- `test_multimodal_messages.py`：带图 `Message` 序列化 → `_to_openai_messages` 输出含 `image_url` data URL。
- `test_desktop_geometry.py`：`cell_center` 数学正确。
- `test_desktop_tools.py`：注入 fake `MouseController` 记录点击，断言点在各格心。
- `test_observer_loop.py`：fake LLM + fake observer，断言 `observe` 在首轮前、每批工具后各调用一次；每次请求只带**一帧最新截图**（旧帧不再出现，不随轮数累积）；工具被执行。
- 全部不碰真屏幕、真 API；真实对局靠 `examples/04_minesweeper_autoplay.py` 手动跑。
- 回归：现有 `tests/test_messages.py` 等在 `Message.content` 类型变宽后仍通过。

## 11. 验收标准

1. 纯文本 agent 行为不变（`observer=None` 时），现有测试全绿。
2. `MODEL=deepseek-flash python examples/04_minesweeper_autoplay.py` 能：截屏 → 标注 → 模型看图 → 调 `click_cell` 真正点击棋盘 → 动作后再次截屏，形成闭环。
3. 模型能在胜利/踩雷后调 `restart_game` 重开，示例层能用 `--games N` 截断。
4. `pytest` 全绿，且不依赖真实屏幕/API。
