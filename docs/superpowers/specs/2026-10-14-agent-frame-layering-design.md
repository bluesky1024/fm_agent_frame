# Agent 框架分层重构设计（框架 / 通用能力 / 应用）

- 日期：2026-10-14
- 状态：待评审
- 类型：架构重构（不改外部行为，只改模块归属与抽象）
- 前置：`2026-09-28-agent-frame-scaffold-design.md`（13 模块骨架）、`2026-10-11-minesweeper-vision-agent-design.md`、`2026-10-12-minesweeper-cross-platform-design.md`

## 1. 背景与目标

扫雷视觉 Agent 引入后，框架包 `src/agent_frame/` 里出现了领域概念，模块层次被打乱。本设计重新划清边界，让框架回到"与领域无关"的定位，让扫雷退回"应用"的位置。

具体要解决的七个问题：

| # | 现状 | 位置 |
|---|---|---|
| 1 | 扫雷的游戏规则提示词与组装函数住在框架包 | `desktop/minesweeper.py` |
| 2 | 通用能力（截屏/输入）与扫雷专属（棋盘几何/网格标注）同住一个目录 | `desktop/` |
| 3 | 扫雷专属工具与通用工具（calculator/time）平级，命名层次不一致 | `tools/desktop/` vs `tools/builtin/` |
| 4 | 通用观察链路焊死扫雷网格，复用度为零 | `desktop/observer.py` |
| 5 | 框架层出现反向隐式依赖：LLM 适配器 import 旁路可观测层 | `llm/openai_compat.py` → `obs/llm_images.py` |
| 6 | 「每轮喂一帧观察」在框架里表现为一个语义宽泛的 `Observer` 协议，且核心循环里长出了视觉分支 | `agent/base.py`、`agent/tool_use.py` |
| 7 | 入口脚本承担应用组装职责，且带 `sys.path` hack | `examples/04_minesweeper_autoplay.py` |

**目标**：仓库呈现清晰的三层（框架 / 通用能力 / 应用），新人按目录名即可判断"这段代码属于谁、能不能复用"；新增第二个视觉应用时，是新增 `apps/xxx/` 目录，而不是修改框架。

## 2. 分层模型

```
① 框架 src/agent_frame/      与领域无关。不知道「扫雷」「棋盘」等词的存在。
② 通用能力 src/agent_frame/computer/
                             框架自带的「计算机使用」能力实现：
                             截屏、鼠标/键盘输入、把屏幕变成一次请求的图片输入。
                             零领域知识：不知道棋盘、不知道网格的语义。
③ 应用 apps/minesweeper/     只认扫雷：游戏本体、棋盘几何、网格标注、
                             规则提示词、扫雷工具、组装函数。
④ 入口 examples/             命令行入口，只做参数拼装与调用。
```

### 依赖方向（硬约束）

| 从 | 到 | 允许 |
|---|---|---|
| `apps/*` | `agent_frame.*` | ✅ |
| `agent_frame.computer` | `agent_frame` 核心（messages / agent 协议 / errors） | ✅ |
| `agent_frame.*`（核心与 computer） | `apps.*` | ❌ 任何情况下都不允许 |

验收标准之一：**全仓库 `grep -rn "minesweeper\|扫雷" src/agent_frame/` 无结果。**

## 3. 目标目录结构

```
fm_agent_frame/
├── src/agent_frame/                    # ① 框架
│   ├── __init__.py  config.py  errors.py  messages.py
│   ├── llm/
│   │   ├── base.py                     # LLMProvider 协议 + ChatResult + ToolSpec
│   │   ├── openai_compat.py            # OpenAICompatProvider
│   │   └── image_store.py              # ★ 由 obs/llm_images.py 迁入
│   ├── tools/
│   │   ├── base.py  registry.py
│   │   └── builtin/                    # calculator, time（仅通用工具）
│   ├── agent/
│   │   ├── base.py                     # Agent 协议 + AgentResult + AgentStep（Observer 删除）
│   │   ├── inputs.py                   # ★ 新增：TextSource / ImageSource / build_turn_messages
│   │   └── tool_use.py                 # ReAct 循环（改收 inputs）
│   ├── computer/                       # ★ ② 通用计算机使用能力（原 desktop/）
│   │   ├── screen.py                   # ScreenCapture + CaptureRegion + 尺度归一化
│   │   ├── input.py                    # InputController + InputBackend + enable_dpi_awareness
│   │   └── sources.py                  # Annotator 协议 + ScreenImageSource + 图像工具
│   ├── memory/  prompt/  obs/  retrieval/  multi_agent/  eval/  server/   # 13 模块骨架不动
├── apps/
│   └── minesweeper/                    # ③ 应用
│       ├── __init__.py
│       ├── board.py                    # 棋盘常量 + BoardGeometry + board_config()
│       ├── grid.py                     # GridAnnotator
│       ├── prompts.py                  # SYSTEM_PROMPT + 图像说明 CAPTION
│       ├── tools.py                    # ClickCellTool / FlagCellTool / RestartGameTool
│       ├── build.py                    # build_registry / build_agent
│       └── game.py                     # tkinter 扫雷（原 games/minesweeper.py）
├── examples/
│   ├── 01_hello_llm.py  02_tool_agent.py  03_interactive.py    # 不变
│   └── 04_minesweeper_autoplay.py       # 瘦身为入口
├── tests/  docs/
```

`games/` 与 `src/agent_frame/desktop/` 两个目录整体消失。

## 4. 核心设计：本轮输入源（`agent/inputs.py`）

### 4.1 两个独立接口

「每轮给 LLM 附带一帧截图」不是特殊机制 —— 它和 Claude 里在一轮对话中传图片一样，本质是**造一条 content 为 `[TextPart, ImagePart]` 的 user 消息**。因此框架不为它发明"观察者"这类宽泛概念，而是定义两个**按模态分开、彼此正交**的输入源接口：

```python
@runtime_checkable
class TextSource(Protocol):
    """文本输入源：产出一段文本。"""
    async def text(self) -> str: ...


@runtime_checkable
class ImageSource(Protocol):
    """图片输入源：产出一张 PNG，并可选地携带「描述这张图」的文本源。"""
    caption: TextSource | None
    async def image(self) -> bytes: ...      # PNG 字节

TurnInput = TextSource | ImageSource
```

两个接口互不感知对方存在：`TextSource` 完全不知道有图片这回事；`ImageSource` 只依赖更小的 `TextSource`。

### 4.2 关联机制：结构性绑定

"一张图 + 关于它的描述"通过 **`ImageSource.caption` 持有那个 `TextSource`** 表达，**不用标签/键配对**。

理由：键配对是运行时字符串魔法，配错要等跑起来才发现，同名还会串。结构性绑定在构造那一刻就固定，配错编译期即报错。

副产品：`StaticText` 一个实现可被两处复用 —— 既作独立文本说明，也作某张图的 caption。**接口独立 ≠ 不能组合。**

### 4.3 组装规则

框架提供纯函数 `build_turn_messages`（可单测，不依赖 Agent）：

```python
async def build_turn_messages(
    sources: Sequence[TurnInput], *, image_detail: str = "high"
) -> list[Message]:
```

| 源 | 产出 |
|---|---|
| `TextSource` | `Message.user(text)` |
| `ImageSource` | `Message.user_with_image(caption?, png, detail=image_detail)` |

规则：

1. **逐源一条消息**，顺序与 `sources` 声明顺序一致。
2. **caption 与图片同处一条消息**：`[TextPart(caption), ImagePart(png)]`，文本在前、图片紧随，使模型把该文本读作这张图的说明。
3. **无 caption**：产出只含 `ImagePart` 的消息，不塞空 `TextPart`。OpenAI 协议允许 content 数组只有 `image_url`。
4. **并发取源**：`asyncio.gather`，结果按原序排列。
5. **单源失败不中断**：该源产出一条 `Message.user("[本轮输入不可用：<原因>]")` 让模型知情，其余源照常。

`image_detail`（"high"/"low"）是**框架级策略**，由 `ToolUseAgent` 参数决定，不作为输入源的属性 —— 它描述的是"这次会话读图要多精细"，不是某个图源的本事。

运行时用 `isinstance(src, ImageSource)` 区分两个协议（二者均为 `@runtime_checkable`）。两个协议的成员不重叠（`text` vs `image` + `caption`），不会误判：`TextSource` 只有 `text`，`ImageSource` 只有 `image` 与 `caption`。

### 4.4 `Message.user_with_image` 的签名调整

```python
@classmethod
def user_with_image(
    cls, text: str | None, png: bytes, *, detail: str = "high"
) -> Message:
```

`text` 由 `str` 放宽为 `str | None`：为 `None` 时不产出 `TextPart`。既有调用（传 `str`）行为不变。

### 4.5 与 Memory 的边界（写进 docstring，不靠记性）

| | Memory | 本轮输入源 |
|---|---|---|
| 生命周期 | **跨轮持久**，会被 save/load | **只活在这一次请求里**，每轮重新产出 |
| 例子 | 对话历史、用户画像 | 屏幕截图（每轮必换） |

`ToolUseAgent.run` 的组装顺序保持不变：

```python
messages = [System(提示词)] + await memory.load(session_id) + [User(task)]   # 持久历史
payload  = messages + await build_turn_messages(self._inputs)                # 本轮输入，临时附加
```

### 4.6 与 `Observer` 的对照

| 旧 | 新 |
|---|---|
| `Observer.observe() -> Message`（宽泛，暗示"谁在观察"） | `TextSource.text()` / `ImageSource.image()`（明确，描述"产出什么输入"） |
| `BoardObserver`（框架协议 + 扫雷网格焊死，单一实现） | `ScreenImageSource`（computer 层，通用）+ `GridAnnotator`（应用层，只负责画） |
| `ToolUseAgent(observer=...)` | `ToolUseAgent(inputs=[...])` |
| 循环中工具执行后显式 `frame = await observe()` | 循环**每轮开头**统一 `build_turn_messages`，天然是"每轮重新取帧" |

`Observer` 协议从 `agent/base.py` 删除。`BoardObserver` 类消失。

### 4.7 通用能力层与应用层的实现形态

`computer/sources.py` —— 通用，零领域知识。它只知道"截一块屏，可选地在图上画点什么，编成 PNG"：

```python
class Annotator(Protocol):
    """在截屏图像上叠加内容。实现方的坐标系应是「图像坐标系」。"""
    def draw(self, img: Image.Image) -> Image.Image: ...


class ScreenImageSource:
    """实现 ImageSource：每轮截一帧屏幕。"""
    def __init__(
        self,
        capture: ScreenCapture,
        *,
        annotator: Annotator | None = None,
        caption: TextSource | None = None,
        max_px: int = 1300,
    ) -> None: ...
    caption: TextSource | None                     # 普通属性，直接透传构造参数
    async def image(self) -> bytes:                # grab → annotator.draw → 下采样 → PNG
        ...
```

`apps/minesweeper/build.py` —— 应用层组装，**坐标平移在这里做**（只有应用同时知道截屏区域与棋盘几何）：

```python
def build_agent(config, llm, *, capture=None, controller=None) -> ToolUseAgent:
    geometry = BoardGeometry(**config["geometry"])
    region = CaptureRegion(**config["region"])
    capture = capture or ScreenCapture(region)
    # 棋盘几何在屏幕坐标系；标注画在图像坐标系 → 按截屏区域左上角平移
    annotator = GridAnnotator(geometry.translated(-region.left, -region.top))
    source = ScreenImageSource(
        capture, annotator=annotator, caption=StaticText(CAPTION)
    )
    return ToolUseAgent(
        llm,
        build_registry(config, controller or InputController()),
        system_prompt=SYSTEM_PROMPT,
        max_steps=config.get("max_steps", 300),
        inputs=[source],
    )
```

三层各就各位：**框架**只说"每轮可以有一批输入消息"；**通用能力**提供"截屏取一帧、可选叠加"；**应用**提供"网格怎么画、坐标怎么平移、说明写什么"。

`ScreenImageSource` 不感知 `GridAnnotator` 的存在 —— 它只依赖 `Annotator` 协议。想给别的应用换一种叠加方式（画十字准星、画包围框），换一个 `Annotator` 实现即可，无需改动 computer 层。

## 5. 文件迁移表

| 现路径 | 去向 | 方式 |
|---|---|---|
| `desktop/screen.py` | `computer/screen.py` | `git mv` |
| `desktop/mouse.py` | `computer/input.py`，类 `MouseController` → `InputController` | `git mv` + 改名 |
| `desktop/observer.py` | 拆入 `computer/sources.py`；`_downscale`/`_to_png` 同去 | 重写 |
| `desktop/geometry.py` | `apps/minesweeper/board.py` | `git mv` |
| `desktop/annotate.py` | `apps/minesweeper/grid.py` | `git mv` |
| `desktop/minesweeper.py` | 拆成 `apps/minesweeper/prompts.py` + `build.py` | 拆分 |
| `tools/desktop/{click_cell,flag_cell,restart_game}.py` | 合并为 `apps/minesweeper/tools.py` | 合并 |
| `games/minesweeper.py` | 拆成 `apps/minesweeper/board.py`（常量 + 几何 + `board_config`）与 `apps/minesweeper/game.py`（`MinesweeperBoard` + `MinesweeperGUI` + `main`） | 拆分 |
| `obs/llm_images.py` | `llm/image_store.py` | `git mv` |
| `agent/base.py` 的 `Observer` | 删除，由 `agent/inputs.py` 取代 | 删除 |
| `examples/04_minesweeper_autoplay.py` | 瘦身为入口（引导 sys.path + 启动游戏 + 调用 `apps.minesweeper.build`） | 重写 |

`MouseController` → `InputController` 的理由：该类除 `click`/`move_to` 外还有 `press(key)`（键盘），叫 Mouse 名不副实。

`apps/minesweeper/game.py` 从 `board.py` 导入棋盘常量，方向为 `game.py → board.py`；不再反向。

## 6. 依赖关系修正

`llm/openai_compat.py` 直接 `import agent_frame.obs.llm_images`，而 `obs` 的定位是旁路可观测层。该文件（把请求里的 base64 落盘成 `log/pic/*.png`）本就是 **LLM 适配器的私事**，迁到 `llm/image_store.py`。修正后：`obs/` 只含 `tracer.py` + `logging_setup.py`，没有任何下游模块依赖它。

## 7. 测试策略与迁移

沿用既有策略：单元测试用 fake `LLMProvider` / fake backend / 注入 grabber，不依赖真实 API 与真实屏幕。

| 现测试文件 | 去向 | 说明 |
|---|---|---|
| `test_desktop_screen.py` | `test_computer_screen.py` | 仅改名 |
| `test_desktop_mouse.py` | `test_computer_input.py` | 改名 + 类名 `InputController` |
| `test_desktop_annotate.py` | `test_minesweeper_grid.py` | 归入应用 |
| `test_desktop_geometry.py` | `test_minesweeper_board.py` | 归入应用 |
| `test_desktop_observer.py` | 拆分见下 | `BoardObserver` 消失 |
| `test_desktop_tools.py` | `test_minesweeper_tools.py` | 归入应用 |
| `test_observer_loop.py` | `test_agent_turn_inputs.py` | `RecordingObserver` → `RecordingText`（实现 `TextSource`）；断言不变 |
| `test_llm_images.py` | `test_llm_image_store.py` | 跟随模块 |
| `test_minesweeper_game.py` | 同路径 | import 改为 `apps.minesweeper.game` / `apps.minesweeper.board` |
| `test_minesweeper_build.py` | 同路径 | import 改为 `apps.minesweeper.build` |

新增测试：

- `tests/test_agent_inputs.py` —— `build_turn_messages` 的组装规则：
  1. 文本源 → 一条 `Message.user`；
  2. 图源（带 caption）→ 一条消息，content 为 `[TextPart, ImagePart]` 且文本在前；
  3. 图源（无 caption）→ 一条只含 `ImagePart` 的消息；
  4. 多源按声明顺序排列；
  5. 单源抛异常 → 该位产出一条"本轮输入不可用"文本消息，其余源不受影响。
- `tests/test_computer_sources.py` —— `ScreenImageSource`：截屏 + 标注 + 下采样 + `caption` 属性透传；`apps` 侧的几何平移断言（原 `test_observer_offsets_geometry_into_image_space`）迁到 `test_minesweeper_build.py`。

## 8. 迁移批次

每批完成后 `pytest` 全绿才进入下一批；全程 `git mv` 保留文件历史。

| 批 | 内容 | 完成标志 |
|---|---|---|
| 1 | 分出应用：建 `apps/minesweeper/`，把领域代码全部迁入，`examples/04` 改指向 | `grep -rn "minesweeper\|扫雷" src/agent_frame/` 无结果 |
| 2 | 通用能力归位：`desktop/` → `computer/`，`MouseController` → `InputController` | 框架包无 `desktop` |
| 3 | 协议替换：删 `Observer`，上 `TextSource`/`ImageSource` 与 `build_turn_messages`，`ToolUseAgent` 改收 `inputs` | 新增 `test_agent_inputs.py` 通过 |
| 4 | 收尾：`obs/llm_images.py` → `llm/image_store.py`；README 模块地图、`docs/minesweeper-agent-flow.md` 更新 | 文档与代码一致 |

## 9. 验证标准

1. `pytest` 全部通过（现有 65 项迁移后仍全绿，另加新增项）。
2. `grep -rn "minesweeper\|扫雷\|BoardGeometry\|GridAnnotator" src/agent_frame/` 无结果。
3. `python -c "import agent_frame, apps.minesweeper.build"` 无副作用（不启动窗口、不截屏）。
4. 端到端真跑一局：`MODEL=deepseek-flash python examples/04_minesweeper_autoplay.py`，Agent 能持续翻格/插旗并推进棋盘。
5. `log/llm.log` 仍全量记录、`log/pic/*.png` 仍落盘（验证第 6 节的迁移没破坏日志链路）。

## 10. 非目标（YAGNI）

- 不实现 `retrieval` / `eval` / `multi_agent` / `server` / `prompt` / `memory` 的待实现部分 —— 13 模块骨架保持原状，本设计只动 `desktop` 的去向与 `agent` 的输入抽象。
- 不做"多图源并发聚合""音频/文件模态"等扩展 —— 现有两个接口已能承载，但**不预建**对应实现。
- 不改 DeepSeek 提供商、不改 LLM 协议转换、不改提示词内容（仅新增/迁移图像说明 `CAPTION` 的存放位置）。
- 不为"任意网格类游戏"抽象出通用棋盘 —— 等第二个应用出现再说。
