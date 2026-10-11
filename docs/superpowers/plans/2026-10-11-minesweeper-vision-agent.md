# 扫雷视觉 Agent 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 `fm_agent_frame` 上新增"多模态计算机使用"能力，并实现一个能在 Windows 上看扫雷截图、控鼠标全自动对局的视觉 Agent。

**Architecture:** 引入框架级 `Observer` 感知扩展点，`ToolUseAgent` 循环在首帧前与每批工具执行后各注入一帧最新截图；`Message` 支持 `text+image` 内容片段，经 `openai_compat` 透传给多模态模型 `deepseek-flash`。新增 `desktop` 模块（截屏/鼠标/几何/标注/观察者）与 `tools/desktop` 工具集（`click_cell`/`flag_cell`/`restart_game`），模型输出 1 基行列号，工具换算成屏幕像素点击。

**Tech Stack:** Python 3.12、async/await、pydantic v2、`typing.Protocol`、pyautogui（鼠标/按键）、mss（截屏）、Pillow（标注）、pytest + pytest-asyncio。

**Spec:** [docs/superpowers/specs/2026-10-11-minesweeper-vision-agent-design.md](../specs/2026-10-11-minesweeper-vision-agent-design.md)

**Windows 提示：** 所有命令用 `python -m pytest`。若在 conda 环境，先 `conda activate py312`。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `pyproject.toml` | 改 | 新增 `desktop` 可选依赖组 |
| `src/agent_frame/messages.py` | 改 | `content` 支持 `TextPart`/`ImagePart`；`Message.user_with_image` |
| `src/agent_frame/llm/openai_compat.py` | 改 | `_to_openai_messages` 透传多模态内容片段 |
| `src/agent_frame/agent/base.py` | 改 | 新增 `Observer` 协议 |
| `src/agent_frame/agent/tool_use.py` | 改 | 循环接入 `observer` 钩子 |
| `src/agent_frame/agent/__init__.py` | 改 | 导出 `Observer` |
| `src/agent_frame/desktop/__init__.py` | 建 | 包导出 |
| `src/agent_frame/desktop/geometry.py` | 建 | `BoardGeometry`：行列号↔屏幕像素 |
| `src/agent_frame/desktop/annotate.py` | 建 | `GridAnnotator`：叠加网格线与行列标尺 |
| `src/agent_frame/desktop/mouse.py` | 建 | `MouseController`（click/move_to/press）+ `enable_dpi_awareness` |
| `src/agent_frame/desktop/screen.py` | 建 | `CaptureRegion` + `ScreenCapture` |
| `src/agent_frame/desktop/observer.py` | 建 | `BoardObserver`：截屏→标注→带图消息 |
| `src/agent_frame/desktop/minesweeper.py` | 建 | `SYSTEM_PROMPT`、`load_config`、`build_registry`、`build_agent` |
| `src/agent_frame/tools/desktop/__init__.py` | 建 | 工具导出 |
| `src/agent_frame/tools/desktop/click_cell.py` | 建 | `ClickCellTool` |
| `src/agent_frame/tools/desktop/flag_cell.py` | 建 | `FlagCellTool` |
| `src/agent_frame/tools/desktop/restart_game.py` | 建 | `RestartGameTool` |
| `config/minesweeper.json` | 建 | 几何/区域/重开配置（需校准） |
| `examples/04_minesweeper_agent.py` | 建 | 组装并跑全自动对局 |
| `tests/test_multimodal_messages.py` | 建 | 多模态消息与透传 |
| `tests/test_observer_loop.py` | 建 | observer 钩子行为 |
| `tests/test_desktop_geometry.py` | 建 | 坐标换算 |
| `tests/test_desktop_annotate.py` | 建 | 标注不崩、尺寸不变 |
| `tests/test_desktop_mouse.py` | 建 | 鼠标控制转发 |
| `tests/test_desktop_screen.py` | 建 | 截屏委托 |
| `tests/test_desktop_observer.py` | 建 | 观察者产图消息 |
| `tests/test_desktop_tools.py` | 建 | 三个工具点击坐标 |
| `tests/test_minesweeper_build.py` | 建 | `build_registry`/`build_agent` 组装 |

**设计约定（务必遵守）：**
- 行列号为 **1 基**：`row` 从上往下 1..rows，`col` 从左往右 1..cols。
- `BoardGeometry.origin_x/origin_y` 是**屏幕绝对物理像素**中棋盘左上角格子的外沿。
- 依赖注入：`MouseController`/`ScreenCapture`/`BoardObserver` 的底层 GUI 库**延迟导入**，测试一律注入 fake，不碰真屏幕。
- 每个任务结束都提交（commit）。

---

## Task 1: 依赖与包骨架

**Files:**
- Modify: `pyproject.toml`
- Create: `src/agent_frame/desktop/__init__.py`
- Create: `src/agent_frame/tools/desktop/__init__.py`

- [ ] **Step 1: 给 pyproject.toml 加 desktop 可选依赖组**

把 `[project.optional-dependencies]` 段改成：

```toml
[project.optional-dependencies]
server = ["fastapi>=0.110", "uvicorn>=0.29"]
desktop = ["pyautogui>=0.9.54", "pillow>=10.0", "mss>=9.0"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
```

- [ ] **Step 2: 创建两个空包文件**

`src/agent_frame/desktop/__init__.py` 先留空：

```python
"""桌面自动化：截屏、鼠标控制、棋盘几何与网格标注。"""
```

`src/agent_frame/tools/desktop/__init__.py` 先留空：

```python
"""桌面自动化工具集（扫雷用）：click_cell / flag_cell / restart_game。"""
```

- [ ] **Step 3: 安装依赖**

Run: `python -m pip install -e ".[desktop,dev]"`
Expected: 成功安装 `pyautogui`、`pillow`、`mss`（可能等待较久）。

- [ ] **Step 4: 验证导入**

Run: `python -c "import PIL, mss, pyautogui, agent_frame.desktop, agent_frame.tools.desktop; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml src/agent_frame/desktop/__init__.py src/agent_frame/tools/desktop/__init__.py
git commit -m "chore: add desktop optional deps and package skeleton"
```

---

## Task 2: Message 多模态 content

**Files:**
- Create: `tests/test_multimodal_messages.py`
- Modify: `src/agent_frame/messages.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_multimodal_messages.py`：

```python
from agent_frame.messages import Message


def test_user_with_image_builds_text_and_image_parts():
    png = b"\x89PNG\r\n\x1a\nfake"
    m = Message.user_with_image("这是棋盘", png, detail="high")

    assert m.role == "user"
    assert isinstance(m.content, list)
    text_part, image_part = m.content
    assert text_part.type == "text"
    assert text_part.text == "这是棋盘"
    assert image_part.type == "image_url"
    assert image_part.image_url["url"].startswith("data:image/png;base64,")
    assert image_part.image_url["detail"] == "high"


def test_plain_text_content_still_works():
    m = Message.user("hi")
    assert m.content == "hi"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_multimodal_messages.py -v`
Expected: FAIL —— `AttributeError: type object 'Message' has no attribute 'user_with_image'`（或导入报错）

- [ ] **Step 3: 修改 messages.py 实现**

把 `src/agent_frame/messages.py` 全文替换为：

```python
"""消息模型：与 OpenAI 兼容协议对齐的消息结构。

DeepSeek 走 OpenAI 兼容协议，一条消息用 role + 可选字段表达：
- system / user：纯文本（content: str）或图文混合（content: list[TextPart|ImagePart]）
- assistant：可能是纯文本（content），也可能是一次工具调用（tool_calls）
- tool：对某次 tool_call 的返回，用 tool_call_id 关联到对应调用
"""

from __future__ import annotations

import base64
from typing import Any, Literal

from pydantic import BaseModel, Field


class TextPart(BaseModel):
    """多模态消息里的文本片段。"""

    type: Literal["text"] = "text"
    text: str


class ImagePart(BaseModel):
    """多模态消息里的图片片段（image_url 内放 data URL 或 http URL）。"""

    type: Literal["image_url"] = "image_url"
    image_url: dict[str, str]


ContentPart = TextPart | ImagePart


class ToolCall(BaseModel):
    """助手发起的一次工具调用。

    arguments 是「已解析」的 dict（内部使用），
    与 OpenAI 线上协议的 JSON 字符串格式的转换见 llm/openai_compat.py。
    """

    id: str = Field(description="本次调用的唯一 ID，tool 消息据此回填结果")
    name: str = Field(description="工具名")
    arguments: dict[str, Any] = Field(default_factory=dict, description="已解析的参数")


class Message(BaseModel):
    """一条对话消息。"""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[TextPart | ImagePart] | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    # ---- 便捷构造 ----
    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role="user", content=content)

    @classmethod
    def user_with_image(
        cls, text: str, png: bytes, *, detail: str = "high"
    ) -> "Message":
        """构造一条「文本 + 内联 PNG 图片」的 user 消息（base64 data URL）。"""
        data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        return cls(
            role="user",
            content=[
                TextPart(text=text),
                ImagePart(image_url={"url": data_url, "detail": detail}),
            ],
        )

    @classmethod
    def assistant(
        cls, content: str | None = None, tool_calls: list[ToolCall] | None = None
    ) -> "Message":
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, tool_call_id: str, content: str, name: str | None = None) -> "Message":
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)
```

- [ ] **Step 4: 运行测试确认通过 + 回归**

Run: `python -m pytest tests/test_multimodal_messages.py tests/test_messages.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/agent_frame/messages.py tests/test_multimodal_messages.py
git commit -m "feat: support multimodal content parts in Message"
```

---

## Task 3: openai_compat 多模态透传

**Files:**
- Modify: `src/agent_frame/llm/openai_compat.py:89-113`
- Modify: `tests/test_multimodal_messages.py`

- [ ] **Step 1: 追加失败测试**

在 `tests/test_multimodal_messages.py` 末尾追加：

```python
from agent_frame.llm.openai_compat import _to_openai_messages


def test_to_openai_messages_emits_multimodal_parts():
    m = Message.user_with_image("棋盘", b"\x89PNG", detail="high")
    out = _to_openai_messages([m])

    assert out[0]["role"] == "user"
    parts = out[0]["content"]
    assert parts[0] == {"type": "text", "text": "棋盘"}
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert parts[1]["image_url"]["detail"] == "high"


def test_to_openai_messages_keeps_text_as_string():
    out = _to_openai_messages([Message.user("hi")])
    assert out[0]["content"] == "hi"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_multimodal_messages.py -v -k multimodal`
Expected: FAIL —— `TypeError`/断言失败（当前实现把 list 直接透传，未 dump 成 dict）

- [ ] **Step 3: 修改 _to_openai_messages**

把 `src/agent_frame/llm/openai_compat.py` 中的 `_to_openai_messages` 函数体里这一段：

```python
        if m.content is not None:
            d["content"] = m.content
```

替换为：

```python
        if m.content is not None:
            if isinstance(m.content, str):
                d["content"] = m.content
            else:
                d["content"] = [part.model_dump() for part in m.content]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_multimodal_messages.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/agent_frame/llm/openai_compat.py tests/test_multimodal_messages.py
git commit -m "feat: pass multimodal content parts through to OpenAI protocol"
```

---

## Task 4: Observer 协议 + ToolUseAgent 钩子

**Files:**
- Create: `tests/test_observer_loop.py`
- Modify: `src/agent_frame/agent/base.py`
- Modify: `src/agent_frame/agent/tool_use.py`
- Modify: `src/agent_frame/agent/__init__.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_observer_loop.py`：

```python
from agent_frame.agent import ToolUseAgent
from agent_frame.llm.base import ChatResult
from agent_frame.messages import Message, ToolCall
from agent_frame.tools import ToolRegistry
from agent_frame.tools.builtin import CalculatorTool


class RecordingObserver:
    def __init__(self) -> None:
        self.count = 0

    async def observe(self) -> Message:
        self.count += 1
        return Message.user(f"frame-{self.count}")


class OneToolThenTextLLM:
    def __init__(self) -> None:
        self.calls = []

    async def chat(self, messages, tools=None):
        self.calls.append(list(messages))
        if len(self.calls) == 1:
            return ChatResult(
                tool_calls=[
                    ToolCall(id="1", name="calculator", arguments={"expression": "2+2"})
                ]
            )
        return ChatResult(content="done")


async def test_observer_injects_frame_before_first_and_after_tool_batch():
    llm = OneToolThenTextLLM()
    obs = RecordingObserver()
    agent = ToolUseAgent(llm, ToolRegistry([CalculatorTool()]), observer=obs)

    await agent.run("play")

    # 首帧 + 一批工具执行后一帧
    assert obs.count == 2
    # 第一轮 chat 收到首帧
    assert llm.calls[0][-1].content == "frame-1"
    # 第二轮 chat 同时含有两帧
    second_contents = [m.content for m in llm.calls[1]]
    assert "frame-1" in second_contents
    assert "frame-2" in second_contents


async def test_no_observer_keeps_default_behavior():
    llm = OneToolThenTextLLM()
    agent = ToolUseAgent(llm, ToolRegistry([CalculatorTool()]))

    result = await agent.run("hi")

    assert result.output == "done"
    assert len(result.steps) == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_observer_loop.py -v`
Expected: FAIL —— `TypeError: __init__() got an unexpected keyword argument 'observer'`

- [ ] **Step 3: 在 agent/base.py 增加 Observer 协议**

在 `src/agent_frame/agent/base.py` 顶部导入区加入 Message 导入，并在文件末尾追加协议：

导入区改为：

```python
from agent_frame.memory.base import Memory
from agent_frame.messages import Message
```

文件末尾追加：

```python
class Observer(Protocol):
    """感知扩展点：每轮为 Agent 提供一条（通常带图的）观察消息。

    实现方按需截屏/采集，返回一条 user Message；返回 None 的场景不需要，
    由调用方决定是否装配观察者。
    """

    async def observe(self) -> Message: ...
```

- [ ] **Step 4: 在 tool_use.py 接入钩子**

把 `src/agent_frame/agent/tool_use.py` 全文替换为：

```python
"""ToolUseAgent：ReAct 风格的「思考 → 调工具 → 观察 → 再思考」循环。

这是整个框架的核心机制：LLM 不直接给出最终答案，
而是先决定「要不要调用工具」，循环直到它给出纯文本回答为止。

可选装配 observer（观察者）：在首轮之前、以及每批工具执行之后，
各注入一条新的观察消息（通常是带图的 user 消息），
从而支持「看 → 做 → 再看」的多模态计算机使用场景。
"""

from __future__ import annotations

from agent_frame.agent.base import AgentResult, AgentStep, Observer
from agent_frame.errors import AgentLoopError
from agent_frame.llm.base import LLMProvider
from agent_frame.memory.base import Memory
from agent_frame.messages import Message
from agent_frame.tools.registry import ToolRegistry


class ToolUseAgent:
    """一个会用工具的 Agent。"""

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        *,
        system_prompt: str | None = None,
        max_steps: int = 8,
        observer: Observer | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._system_prompt = system_prompt
        self._max_steps = max_steps
        self._observer = observer

    async def run(
        self,
        task: str,
        *,
        memory: Memory | None = None,
        session_id: str = "default",
    ) -> AgentResult:
        """处理一次用户输入（单轮）。

        传入同一个 memory + session_id 即可实现多轮对话：每次都会先
        load 该会话的历史，跑完再 save 回去。
        """
        messages: list[Message] = []
        if self._system_prompt:
            messages.append(Message.system(self._system_prompt))
        if memory is not None:
            messages.extend(await memory.load(session_id))
        messages.append(Message.user(task))
        if self._observer is not None:
            messages.append(await self._observer.observe())

        tool_specs = self._tools.to_tool_specs()
        steps: list[AgentStep] = []

        for index in range(self._max_steps):
            result = await self._llm.chat(messages, tool_specs)

            # LLM 决定调用工具：逐个执行，把结果作为 tool 消息回填，进入下一轮
            if result.has_tool_calls and result.tool_calls:
                messages.append(Message.assistant(tool_calls=result.tool_calls))
                called: list[str] = []
                for tc in result.tool_calls:
                    try:
                        output = await self._tools.call(tc.name, tc.arguments)
                    except Exception as exc:  # noqa: BLE001 - 工具异常回填给 LLM 让其修正
                        output = f"工具执行出错: {exc}"
                    messages.append(
                        Message.tool(tool_call_id=tc.id, content=output, name=tc.name)
                    )
                    called.append(tc.name)
                steps.append(AgentStep(index=index, tool_calls=called))
                if self._observer is not None:
                    messages.append(await self._observer.observe())
                continue

            # LLM 给出最终文本回答
            final = result.content or ""
            messages.append(Message.assistant(content=final))
            steps.append(AgentStep(index=index, content=final))
            if memory is not None:
                await memory.save(session_id, messages)
            return AgentResult(output=final, steps=steps)

        raise AgentLoopError(f"超过最大步数 {self._max_steps} 仍未收敛")
```

- [ ] **Step 5: 导出 Observer**

把 `src/agent_frame/agent/__init__.py` 全文替换为：

```python
from agent_frame.agent.base import Agent, AgentResult, AgentStep, Observer
from agent_frame.agent.tool_use import ToolUseAgent

__all__ = ["Agent", "AgentResult", "AgentStep", "Observer", "ToolUseAgent"]
```

- [ ] **Step 6: 运行测试确认通过 + 全量回归**

Run: `python -m pytest -v`
Expected: 全部 PASS（含既有 `test_agent.py`）

- [ ] **Step 7: 提交**

```bash
git add src/agent_frame/agent/base.py src/agent_frame/agent/tool_use.py src/agent_frame/agent/__init__.py tests/test_observer_loop.py
git commit -m "feat: add Observer perception hook to ToolUseAgent loop"
```

---

## Task 5: BoardGeometry 坐标换算

**Files:**
- Create: `tests/test_desktop_geometry.py`
- Create: `src/agent_frame/desktop/geometry.py`
- Modify: `src/agent_frame/desktop/__init__.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_desktop_geometry.py`：

```python
import pytest

from agent_frame.desktop.geometry import BoardGeometry


def _geo() -> BoardGeometry:
    return BoardGeometry(
        origin_x=100, origin_y=200, cell_w=20, cell_h=24, rows=9, cols=9
    )


def test_cell_center_is_one_based():
    g = _geo()
    assert g.cell_center(1, 1) == (110, 212)
    assert g.cell_center(2, 3) == (150, 236)


def test_cell_center_out_of_range_raises():
    g = _geo()
    with pytest.raises(ValueError):
        g.cell_center(10, 1)


def test_cell_center_zero_or_negative_raises():
    g = _geo()
    with pytest.raises(ValueError):
        g.cell_center(1, 0)


def test_translated_shifts_origin_only():
    g = _geo()
    moved = g.translated(-100, -200)
    assert moved.origin_x == 0
    assert moved.origin_y == 0
    assert moved.cell_center(1, 1) == (10, 12)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_desktop_geometry.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'agent_frame.desktop.geometry'`

- [ ] **Step 3: 实现 geometry.py**

创建 `src/agent_frame/desktop/geometry.py`：

```python
"""棋盘几何：行列号 ↔ 屏幕像素坐标换算。"""

from __future__ import annotations

from pydantic import BaseModel


class BoardGeometry(BaseModel):
    """棋盘在屏幕上的几何布局。

    origin_x/origin_y 是左上角格子外沿的屏幕绝对物理像素；
    cell_w/cell_h 是单格宽高；行列号约定为 1 基。
    """

    origin_x: int
    origin_y: int
    cell_w: int
    cell_h: int
    rows: int
    cols: int

    def cell_center(self, row: int, col: int) -> tuple[int, int]:
        """把 1 基行列号换算成屏幕像素的格子中心坐标。"""
        if not (1 <= row <= self.rows):
            raise ValueError(f"行号越界: {row}，合法范围 1..{self.rows}")
        if not (1 <= col <= self.cols):
            raise ValueError(f"列号越界: {col}，合法范围 1..{self.cols}")
        x = self.origin_x + (col - 1) * self.cell_w + self.cell_w // 2
        y = self.origin_y + (row - 1) * self.cell_h + self.cell_h // 2
        return x, y

    def translated(self, dx: int, dy: int) -> "BoardGeometry":
        """返回平移后的副本（只改原点）。用于把屏幕坐标映射到截屏图像坐标。"""
        return self.model_copy(
            update={"origin_x": self.origin_x + dx, "origin_y": self.origin_y + dy}
        )
```

- [ ] **Step 4: 更新 desktop/__init__.py 导出**

把 `src/agent_frame/desktop/__init__.py` 全文替换为：

```python
"""桌面自动化：截屏、鼠标控制、棋盘几何与网格标注。"""

from agent_frame.desktop.geometry import BoardGeometry

__all__ = ["BoardGeometry"]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_desktop_geometry.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add src/agent_frame/desktop/geometry.py src/agent_frame/desktop/__init__.py tests/test_desktop_geometry.py
git commit -m "feat: add BoardGeometry row/col to pixel mapping"
```

---

## Task 6: GridAnnotator 网格标注

**Files:**
- Create: `tests/test_desktop_annotate.py`
- Create: `src/agent_frame/desktop/annotate.py`
- Modify: `src/agent_frame/desktop/__init__.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_desktop_annotate.py`：

```python
from PIL import Image

from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry


def _geo() -> BoardGeometry:
    return BoardGeometry(
        origin_x=10, origin_y=10, cell_w=8, cell_h=8, rows=3, cols=3
    )


def test_draw_preserves_size_and_mode():
    img = Image.new("RGB", (60, 60), "white")
    out = GridAnnotator(_geo()).draw(img)
    assert out.size == (60, 60)
    assert out.mode == "RGB"


def test_draw_modifies_pixels_inside_grid():
    img = Image.new("RGB", (60, 60), "white")
    out = GridAnnotator(_geo()).draw(img)
    # 网格线画在 x=10 处，应出现非白像素
    assert out.getpixel((10, 10)) != (255, 255, 255)


def test_draw_does_not_mutate_input():
    img = Image.new("RGB", (60, 60), "white")
    GridAnnotator(_geo()).draw(img)
    assert img.getpixel((10, 10)) == (255, 255, 255)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_desktop_annotate.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'agent_frame.desktop.annotate'`

- [ ] **Step 3: 实现 annotate.py**

创建 `src/agent_frame/desktop/annotate.py`：

```python
"""网格标注：在棋盘截图上叠加网格线与行列标尺，供视觉模型读取行列号。"""

from __future__ import annotations

from PIL import Image, ImageDraw

from agent_frame.desktop.geometry import BoardGeometry

_LINE = (255, 0, 0)
_LABEL = (0, 0, 255)


class GridAnnotator:
    """按几何在图像上画网格线和 1 基行列标尺。

    传入的几何应处于「图像坐标系」（即已按截屏区域偏移过）。
    """

    def __init__(self, geometry: BoardGeometry) -> None:
        self.geometry = geometry

    def draw(self, img: Image.Image) -> Image.Image:
        out = img.convert("RGB").copy()
        draw = ImageDraw.Draw(out)
        g = self.geometry

        right = g.origin_x + g.cols * g.cell_w
        bottom = g.origin_y + g.rows * g.cell_h

        # 竖线（列边界）
        for c in range(g.cols + 1):
            x = g.origin_x + c * g.cell_w
            draw.line([(x, g.origin_y), (x, bottom)], fill=_LINE, width=2)
        # 横线（行边界）
        for r in range(g.rows + 1):
            y = g.origin_y + r * g.cell_h
            draw.line([(g.origin_x, y), (right, y)], fill=_LINE, width=2)

        # 行号（左侧，1 基）
        for r in range(1, g.rows + 1):
            y = g.origin_y + (r - 1) * g.cell_h + g.cell_h // 2
            draw.text((g.origin_x - 18, y - 6), str(r), fill=_LABEL)
        # 列号（顶部，1 基）
        for c in range(1, g.cols + 1):
            x = g.origin_x + (c - 1) * g.cell_w + g.cell_w // 2
            draw.text((x - 4, g.origin_y - 16), str(c), fill=_LABEL)

        return out
```

- [ ] **Step 4: 更新 desktop/__init__.py 导出**

把 `src/agent_frame/desktop/__init__.py` 全文替换为：

```python
"""桌面自动化：截屏、鼠标控制、棋盘几何与网格标注。"""

from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry

__all__ = ["BoardGeometry", "GridAnnotator"]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_desktop_annotate.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add src/agent_frame/desktop/annotate.py src/agent_frame/desktop/__init__.py tests/test_desktop_annotate.py
git commit -m "feat: add GridAnnotator for board grid overlay"
```

---

## Task 7: MouseController + DPI

**Files:**
- Create: `tests/test_desktop_mouse.py`
- Create: `src/agent_frame/desktop/mouse.py`
- Modify: `src/agent_frame/desktop/__init__.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_desktop_mouse.py`：

```python
from agent_frame.desktop.mouse import MouseController, enable_dpi_awareness


class FakeBackend:
    def __init__(self) -> None:
        self.clicks = []
        self.moves = []
        self.presses = []

    def click(self, x, y, button):
        self.clicks.append((x, y, button))

    def moveTo(self, x, y):
        self.moves.append((x, y))

    def press(self, key):
        self.presses.append(key)


def test_click_forwards_to_backend():
    b = FakeBackend()
    m = MouseController(backend=b)
    m.click(10, 20)
    m.click(30, 40, button="right")
    assert b.clicks == [(10, 20, "left"), (30, 40, "right")]


def test_move_to_forwards_to_backend():
    b = FakeBackend()
    MouseController(backend=b).move_to(5, 6)
    assert b.moves == [(5, 6)]


def test_press_forwards_to_backend():
    b = FakeBackend()
    MouseController(backend=b).press("f2")
    assert b.presses == ["f2"]


def test_enable_dpi_awareness_does_not_raise():
    enable_dpi_awareness()  # 非 Windows 平台为 no-op，不应抛异常
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_desktop_mouse.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'agent_frame.desktop.mouse'`

- [ ] **Step 3: 实现 mouse.py**

创建 `src/agent_frame/desktop/mouse.py`：

```python
"""鼠标与按键控制（基于 pyautogui），以及 Windows 高 DPI 对齐。"""

from __future__ import annotations

import sys
from typing import Protocol


class InputBackend(Protocol):
    """pyautogui 所需的最小接口；测试用 fake 实现。"""

    def click(self, x: int, y: int, button: str) -> None: ...
    def moveTo(self, x: int, y: int) -> None: ...
    def press(self, key: str) -> None: ...


def enable_dpi_awareness() -> None:
    """Windows 高 DPI 下让屏幕坐标对齐物理像素；非 Windows 为 no-op。

    必须在使用坐标点击前调用，否则缩放会把点击位置带偏。
    """
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
    except Exception:  # noqa: BLE001 - 老系统回退到 system DPI aware
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


class MouseController:
    """把点击/移动/按键转发给底层后端（默认 pyautogui）。"""

    def __init__(self, backend: InputBackend | None = None) -> None:
        self._backend = backend or _default_backend()

    def click(self, x: int, y: int, *, button: str = "left") -> None:
        self._backend.click(x, y, button)

    def move_to(self, x: int, y: int) -> None:
        self._backend.moveTo(x, y)

    def press(self, key: str) -> None:
        self._backend.press(key)


def _default_backend() -> InputBackend:
    import pyautogui  # 延迟导入，避免测试环境需要 GUI 依赖

    return pyautogui
```

- [ ] **Step 4: 更新 desktop/__init__.py 导出**

把 `src/agent_frame/desktop/__init__.py` 全文替换为：

```python
"""桌面自动化：截屏、鼠标控制、棋盘几何与网格标注。"""

from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController, enable_dpi_awareness

__all__ = ["BoardGeometry", "GridAnnotator", "MouseController", "enable_dpi_awareness"]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_desktop_mouse.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add src/agent_frame/desktop/mouse.py src/agent_frame/desktop/__init__.py tests/test_desktop_mouse.py
git commit -m "feat: add MouseController and DPI awareness"
```

---

## Task 8: ScreenCapture 截屏

**Files:**
- Create: `tests/test_desktop_screen.py`
- Create: `src/agent_frame/desktop/screen.py`
- Modify: `src/agent_frame/desktop/__init__.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_desktop_screen.py`：

```python
from PIL import Image

from agent_frame.desktop.screen import CaptureRegion, ScreenCapture


def test_grab_delegates_to_grabber_with_region():
    region = CaptureRegion(left=10, top=20, width=30, height=40)
    seen = {}

    def fake_grabber(r):
        seen["region"] = r
        return Image.new("RGB", (r.width, r.height), "white")

    cap = ScreenCapture(region, grabber=fake_grabber)
    img = cap.grab()

    assert img.size == (30, 40)
    assert seen["region"] is region
    assert cap.region == region
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_desktop_screen.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'agent_frame.desktop.screen'`

- [ ] **Step 3: 实现 screen.py**

创建 `src/agent_frame/desktop/screen.py`：

```python
"""截屏：把屏幕上一块矩形区域抓成 PIL 图像。"""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image
from pydantic import BaseModel


class CaptureRegion(BaseModel):
    """截屏区域（屏幕绝对像素）。"""

    left: int
    top: int
    width: int
    height: int


Grabber = Callable[[CaptureRegion], Image.Image]


class ScreenCapture:
    """按区域截屏。默认用 mss；测试可注入 grabber。"""

    def __init__(self, region: CaptureRegion, grabber: Grabber | None = None) -> None:
        self._region = region
        self._grab = grabber or _default_grabber

    @property
    def region(self) -> CaptureRegion:
        return self._region

    def grab(self) -> Image.Image:
        return self._grab(self._region)


def _default_grabber(region: CaptureRegion) -> Image.Image:
    import mss  # 延迟导入，避免测试环境需要截屏依赖

    with mss.mss() as sct:
        shot = sct.grab(
            {
                "left": region.left,
                "top": region.top,
                "width": region.width,
                "height": region.height,
            }
        )
        return Image.frombytes("RGB", shot.size, shot.rgb)
```

- [ ] **Step 4: 更新 desktop/__init__.py 导出**

把 `src/agent_frame/desktop/__init__.py` 全文替换为：

```python
"""桌面自动化：截屏、鼠标控制、棋盘几何与网格标注。"""

from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController, enable_dpi_awareness
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture

__all__ = [
    "BoardGeometry",
    "CaptureRegion",
    "GridAnnotator",
    "MouseController",
    "ScreenCapture",
    "enable_dpi_awareness",
]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_desktop_screen.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add src/agent_frame/desktop/screen.py src/agent_frame/desktop/__init__.py tests/test_desktop_screen.py
git commit -m "feat: add ScreenCapture region grabbing"
```

---

## Task 9: BoardObserver 观察者

**Files:**
- Create: `tests/test_desktop_observer.py`
- Create: `src/agent_frame/desktop/observer.py`
- Modify: `src/agent_frame/desktop/__init__.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_desktop_observer.py`：

```python
from PIL import Image

from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.observer import BoardObserver
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture


def _capture(left=0, top=0, w=200, h=200) -> ScreenCapture:
    region = CaptureRegion(left=left, top=top, width=w, height=h)
    return ScreenCapture(
        region, grabber=lambda r: Image.new("RGB", (r.width, r.height), "white")
    )


def _geo(origin_x=20, origin_y=20) -> BoardGeometry:
    return BoardGeometry(
        origin_x=origin_x, origin_y=origin_y, cell_w=10, cell_h=10, rows=9, cols=9
    )


async def test_observe_returns_image_user_message():
    obs = BoardObserver(_capture(), _geo())
    msg = await obs.observe()

    assert msg.role == "user"
    assert isinstance(msg.content, list)
    text_part, image_part = msg.content
    assert "棋盘" in text_part.text
    assert image_part.type == "image_url"
    assert image_part.image_url["url"].startswith("data:image/png;base64,")
    assert image_part.image_url["detail"] == "high"


async def test_observe_offsets_geometry_into_image_space():
    # 截屏区域从 (50,60) 开始，几何原点也是 (50,60) → 图像空间应为 (0,0)
    obs = BoardObserver(_capture(left=50, top=60, w=100, h=100), _geo(50, 60))
    assert obs.annotator.geometry.origin_x == 0
    assert obs.annotator.geometry.origin_y == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_desktop_observer.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'agent_frame.desktop.observer'`

- [ ] **Step 3: 实现 observer.py**

创建 `src/agent_frame/desktop/observer.py`：

```python
"""BoardObserver：截屏 → 叠加网格 → 组装成带图 user 消息。"""

from __future__ import annotations

import io

from PIL import Image

from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.screen import ScreenCapture
from agent_frame.messages import Message

_DEFAULT_CAPTION = (
    "这是当前扫雷棋盘的截图，每个格子外侧已标注 1 基行列号。"
    "请根据棋盘状态决定下一步动作。"
)


class BoardObserver:
    """实现 Observer 协议：每轮提供一帧最新棋盘图。"""

    def __init__(
        self,
        capture: ScreenCapture,
        geometry: BoardGeometry,
        *,
        detail: str = "high",
        max_px: int = 1300,
        caption: str = _DEFAULT_CAPTION,
    ) -> None:
        self._capture = capture
        # 把屏幕绝对坐标平移到截屏图像坐标，供标注使用
        offset = geometry.translated(-capture.region.left, -capture.region.top)
        self.annotator = GridAnnotator(offset)
        self._detail = detail
        self._max_px = max_px
        self._caption = caption

    async def observe(self) -> Message:
        img = self._capture.grab()
        img = self.annotator.draw(img)
        img = _downscale(img, self._max_px)
        return Message.user_with_image(
            self._caption, _to_png(img), detail=self._detail
        )


def _downscale(img: Image.Image, max_px: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_px:
        return img
    scale = max_px / max(w, h)
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))))


def _to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

- [ ] **Step 4: 更新 desktop/__init__.py 导出**

把 `src/agent_frame/desktop/__init__.py` 全文替换为：

```python
"""桌面自动化：截屏、鼠标控制、棋盘几何与网格标注。"""

from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController, enable_dpi_awareness
from agent_frame.desktop.observer import BoardObserver
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture

__all__ = [
    "BoardGeometry",
    "BoardObserver",
    "CaptureRegion",
    "GridAnnotator",
    "MouseController",
    "ScreenCapture",
    "enable_dpi_awareness",
]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_desktop_observer.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add src/agent_frame/desktop/observer.py src/agent_frame/desktop/__init__.py tests/test_desktop_observer.py
git commit -m "feat: add BoardObserver producing annotated image messages"
```

---

## Task 10: 扫雷工具集

**Files:**
- Create: `tests/test_desktop_tools.py`
- Create: `src/agent_frame/tools/desktop/click_cell.py`
- Create: `src/agent_frame/tools/desktop/flag_cell.py`
- Create: `src/agent_frame/tools/desktop/restart_game.py`
- Modify: `src/agent_frame/tools/desktop/__init__.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_desktop_tools.py`：

```python
import pytest

from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController
from agent_frame.tools.desktop import ClickCellTool, FlagCellTool, RestartGameTool


class FakeBackend:
    def __init__(self) -> None:
        self.clicks = []
        self.presses = []

    def click(self, x, y, button):
        self.clicks.append((x, y, button))

    def moveTo(self, x, y):
        pass

    def press(self, key):
        self.presses.append(key)


def _geo() -> BoardGeometry:
    return BoardGeometry(origin_x=0, origin_y=0, cell_w=10, cell_h=10, rows=9, cols=9)


async def test_click_cell_clicks_cell_center():
    b = FakeBackend()
    tool = ClickCellTool(_geo(), MouseController(backend=b))
    out = await tool.run(row=2, col=3)
    assert b.clicks == [(25, 15, "left")]
    assert "2, 3" in out


async def test_flag_cell_right_clicks_cell_center():
    b = FakeBackend()
    tool = FlagCellTool(_geo(), MouseController(backend=b))
    out = await tool.run(row=1, col=1)
    assert b.clicks == [(5, 5, "right")]
    assert "1, 1" in out


async def test_restart_game_by_click():
    b = FakeBackend()
    tool = RestartGameTool(MouseController(backend=b), click_xy=(100, 100))
    out = await tool.run()
    assert b.clicks == [(100, 100, "left")]
    assert "100" in out


async def test_restart_game_by_key():
    b = FakeBackend()
    tool = RestartGameTool(MouseController(backend=b), key="f2")
    out = await tool.run()
    assert b.presses == ["f2"]
    assert "f2" in out


def test_restart_game_requires_exactly_one_action():
    with pytest.raises(Exception):
        RestartGameTool(MouseController(backend=FakeBackend()))
    with pytest.raises(Exception):
        RestartGameTool(
            MouseController(backend=FakeBackend()), click_xy=(1, 1), key="f2"
        )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_desktop_tools.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'agent_frame.tools.desktop'`（或导入名缺失）

- [ ] **Step 3: 实现 click_cell.py**

创建 `src/agent_frame/tools/desktop/click_cell.py`：

```python
"""工具：翻开指定格子（左键单击）。"""

from __future__ import annotations

from typing import Any, ClassVar

from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController


class ClickCellTool:
    name: ClassVar[str] = "click_cell"
    description: ClassVar[str] = (
        "翻开指定的格子（左键单击该格中心）。row/col 为 1 基行列号，"
        "与棋盘截图上标注的行列号一致。"
    )
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "row": {"type": "integer", "description": "行号（1 基，从上往下）"},
            "col": {"type": "integer", "description": "列号（1 基，从左往右）"},
        },
        "required": ["row", "col"],
    }

    def __init__(self, geometry: BoardGeometry, mouse: MouseController) -> None:
        self._geometry = geometry
        self._mouse = mouse

    async def run(self, row: int, col: int) -> str:
        x, y = self._geometry.cell_center(row, col)
        self._mouse.click(x, y, button="left")
        return f"已翻开格子 ({row}, {col})，点击坐标 ({x}, {y})"
```

- [ ] **Step 4: 实现 flag_cell.py**

创建 `src/agent_frame/tools/desktop/flag_cell.py`：

```python
"""工具：给指定格子插旗（右键单击）。"""

from __future__ import annotations

from typing import Any, ClassVar

from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController


class FlagCellTool:
    name: ClassVar[str] = "flag_cell"
    description: ClassVar[str] = (
        "给指定的格子插旗（右键单击该格中心），表示此处是雷。"
        "row/col 为 1 基行列号，与棋盘截图上标注的行列号一致。"
    )
    parameters: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "row": {"type": "integer", "description": "行号（1 基，从上往下）"},
            "col": {"type": "integer", "description": "列号（1 基，从左往右）"},
        },
        "required": ["row", "col"],
    }

    def __init__(self, geometry: BoardGeometry, mouse: MouseController) -> None:
        self._geometry = geometry
        self._mouse = mouse

    async def run(self, row: int, col: int) -> str:
        x, y = self._geometry.cell_center(row, col)
        self._mouse.click(x, y, button="right")
        return f"已给格子 ({row}, {col}) 插旗，点击坐标 ({x}, {y})"
```

- [ ] **Step 5: 实现 restart_game.py**

创建 `src/agent_frame/tools/desktop/restart_game.py`：

```python
"""工具：重开一局（点击重开按钮或发按键）。"""

from __future__ import annotations

from typing import Any, ClassVar

from agent_frame.desktop.mouse import MouseController
from agent_frame.errors import ToolError


class RestartGameTool:
    name: ClassVar[str] = "restart_game"
    description: ClassVar[str] = (
        "当本局已经结束（胜利，或踩到雷）时调用，重开一局新游戏。"
        "棋盘未结束时不要调用。"
    )
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    def __init__(
        self,
        mouse: MouseController,
        *,
        click_xy: tuple[int, int] | None = None,
        key: str | None = None,
    ) -> None:
        if (click_xy is None) == (key is None):
            raise ToolError("restart_game 需要且仅需一种重开方式：click_xy 或 key")
        self._mouse = mouse
        self._click_xy = click_xy
        self._key = key

    async def run(self) -> str:
        if self._click_xy is not None:
            x, y = self._click_xy
            self._mouse.click(x, y, button="left")
            return f"已点击重开按钮 ({x}, {y})"
        self._mouse.press(self._key)  # type: ignore[arg-type]
        return f"已按下重开按键 {self._key}"
```

- [ ] **Step 6: 更新 tools/desktop/__init__.py 导出**

把 `src/agent_frame/tools/desktop/__init__.py` 全文替换为：

```python
"""桌面自动化工具集（扫雷用）：click_cell / flag_cell / restart_game。"""

from agent_frame.tools.desktop.click_cell import ClickCellTool
from agent_frame.tools.desktop.flag_cell import FlagCellTool
from agent_frame.tools.desktop.restart_game import RestartGameTool

__all__ = ["ClickCellTool", "FlagCellTool", "RestartGameTool"]
```

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m pytest tests/test_desktop_tools.py -v`
Expected: 全部 PASS

- [ ] **Step 8: 提交**

```bash
git add src/agent_frame/tools/desktop/ tests/test_desktop_tools.py
git commit -m "feat: add minesweeper tools (click_cell/flag_cell/restart_game)"
```

---

## Task 11: 配置 + 组装 + 示例

**Files:**
- Create: `config/minesweeper.json`
- Create: `tests/test_minesweeper_build.py`
- Create: `src/agent_frame/desktop/minesweeper.py`
- Create: `examples/04_minesweeper_agent.py`
- Modify: `src/agent_frame/desktop/__init__.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_minesweeper_build.py`：

```python
from PIL import Image

from agent_frame.desktop.minesweeper import build_agent, build_registry
from agent_frame.desktop.mouse import MouseController
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture


class FakeBackend:
    def click(self, x, y, button):
        pass

    def moveTo(self, x, y):
        pass

    def press(self, key):
        pass


def _config() -> dict:
    return {
        "geometry": {
            "origin_x": 0,
            "origin_y": 0,
            "cell_w": 10,
            "cell_h": 10,
            "rows": 9,
            "cols": 9,
        },
        "region": {"left": 0, "top": 0, "width": 100, "height": 100},
        "restart": {"type": "click", "x": 50, "y": 50},
        "image_detail": "high",
        "image_max_px": 1300,
        "max_steps": 300,
    }


def test_build_registry_has_three_tools():
    reg = build_registry(_config(), MouseController(backend=FakeBackend()))
    assert set(reg.names()) == {"click_cell", "flag_cell", "restart_game"}


def test_build_registry_supports_key_restart():
    cfg = _config()
    cfg["restart"] = {"type": "key", "key": "f2"}
    reg = build_registry(cfg, MouseController(backend=FakeBackend()))
    assert "restart_game" in reg.names()


def test_build_agent_assembles_without_touching_screen():
    cap = ScreenCapture(
        CaptureRegion(left=0, top=0, width=100, height=100),
        grabber=lambda r: Image.new("RGB", (r.width, r.height), "white"),
    )
    mouse = MouseController(backend=FakeBackend())
    agent = build_agent(_config(), llm=object(), mouse=mouse, capture=cap)
    assert agent is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_minesweeper_build.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'agent_frame.desktop.minesweeper'`

- [ ] **Step 3: 实现 minesweeper.py**

创建 `src/agent_frame/desktop/minesweeper.py`：

```python
"""扫雷 Agent 的组装：系统提示词、配置加载、工具注册与 Agent 构建。"""

from __future__ import annotations

import json
from pathlib import Path

from agent_frame.agent import ToolUseAgent
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController
from agent_frame.desktop.observer import BoardObserver
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture
from agent_frame.tools import ToolRegistry
from agent_frame.tools.desktop import ClickCellTool, FlagCellTool, RestartGameTool

SYSTEM_PROMPT = """你是一个扫雷专家，正在通过截图观察一款扫雷游戏并操作鼠标通关。

每一轮你都会收到一张最新棋盘截图，格子外侧标注了行列号（1 基：行自上而下、列自左而右）。
棋盘上：数字表示该格周围 8 格的雷数；空白表示周围无雷；带旗帜的格子是你已标记的雷。

可用工具：
- click_cell(row, col)：翻开一个格子（当你确定它安全时）。
- flag_cell(row, col)：插旗标记一个格子为雷。
- restart_game()：仅当本局已经结束（胜利，或已踩到雷）时调用，重开新局。

策略：
- 若某数字等于其周围未翻开格数量，则这些未翻开格全是雷，用 flag_cell 全部插旗。
- 若某数字等于其周围已插旗数量，则其余未翻开格安全，用 click_cell 全部翻开。
- 无法确定时，选择周围约束下最可能安全的格子翻开（不要乱猜高风险格）。
- 一轮里可以批量输出多个确定的动作以节省开销。
- 每步只依据最新截图决策；看不到进展时优先做确定性的翻开/插旗。

注意：本局结束时必须调用 restart_game 开新局，继续游戏。"""


def load_config(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_registry(config: dict, mouse: MouseController) -> ToolRegistry:
    geometry = BoardGeometry(**config["geometry"])
    restart = config["restart"]
    if restart["type"] == "click":
        restart_tool = RestartGameTool(mouse, click_xy=(restart["x"], restart["y"]))
    else:
        restart_tool = RestartGameTool(mouse, key=restart["key"])
    return ToolRegistry(
        [ClickCellTool(geometry, mouse), FlagCellTool(geometry, mouse), restart_tool]
    )


def build_agent(
    config: dict,
    llm,
    *,
    mouse: MouseController | None = None,
    capture: ScreenCapture | None = None,
) -> ToolUseAgent:
    geometry = BoardGeometry(**config["geometry"])
    region = CaptureRegion(**config["region"])
    mouse = mouse or MouseController()
    capture = capture or ScreenCapture(region)
    observer = BoardObserver(
        capture,
        geometry,
        detail=config.get("image_detail", "high"),
        max_px=config.get("image_max_px", 1300),
    )
    registry = build_registry(config, mouse)
    return ToolUseAgent(
        llm,
        registry,
        system_prompt=SYSTEM_PROMPT,
        max_steps=config.get("max_steps", 300),
        observer=observer,
    )
```

- [ ] **Step 4: 创建 config/minesweeper.json**

创建 `config/minesweeper.json`（数值为**占位示例**，实现后须用真实截图校准）：

```json
{
  "_comment": "校准说明：origin_x/origin_y 是棋盘左上角格子外沿的屏幕绝对像素；cell_w/cell_h 是单格宽高；region 是截屏区域。restart 支持 type=click(x,y) 或 type=key(key)。用一张目标扫雷截图量出这些数值后替换。",
  "geometry": { "origin_x": 380, "origin_y": 260, "cell_w": 24, "cell_h": 24, "rows": 9, "cols": 9 },
  "region": { "left": 340, "top": 220, "width": 280, "height": 280 },
  "restart": { "type": "click", "x": 470, "y": 230 },
  "image_detail": "high",
  "image_max_px": 1300,
  "max_steps": 300
}
```

- [ ] **Step 5: 创建 examples/04_minesweeper_agent.py**

创建 `examples/04_minesweeper_agent.py`：

```python
"""示例 4：扫雷视觉 Agent（多模态计算机使用）。

让 Agent 反复：截取扫雷棋盘截图 → 看图决策 → 控制鼠标点击/插旗 → 再看，
直到赢下或踩雷后自动重开，持续对局。

运行：
    MODEL=deepseek-flash python examples/04_minesweeper_agent.py
前提：
    - 已设置 DEEPSEEK_API_KEY（环境变量或 .env）。
    - 已校准 config/minesweeper.json 的几何/区域/重开参数。
    - 目标扫雷窗口保持在校准时的位置与大小（本期假设窗口固定不移动）。
停止：Ctrl+C。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from agent_frame.config import get_settings
from agent_frame.desktop.minesweeper import build_agent, load_config
from agent_frame.desktop.mouse import enable_dpi_awareness
from agent_frame.llm import OpenAICompatProvider
from agent_frame.obs import setup_logging

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "minesweeper.json"


async def main() -> None:
    enable_dpi_awareness()
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir, console=settings.log_console)

    config = load_config(CONFIG_PATH)
    llm = OpenAICompatProvider(settings)
    agent = build_agent(config, llm)

    print(f"开始自动扫雷（模型={settings.model}，Ctrl+C 停止）...")
    result = await agent.run("赢下这局扫雷。")
    print("\n===== 结束 =====")
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: 更新 desktop/__init__.py 导出组装函数**

把 `src/agent_frame/desktop/__init__.py` 全文替换为：

```python
"""桌面自动化：截屏、鼠标控制、棋盘几何与网格标注。"""

from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.desktop.mouse import MouseController, enable_dpi_awareness
from agent_frame.desktop.observer import BoardObserver
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture
from agent_frame.desktop.minesweeper import build_agent, build_registry, load_config

__all__ = [
    "BoardGeometry",
    "BoardObserver",
    "CaptureRegion",
    "GridAnnotator",
    "MouseController",
    "ScreenCapture",
    "build_agent",
    "build_registry",
    "enable_dpi_awareness",
    "load_config",
]
```

- [ ] **Step 7: 运行测试确认通过 + 全量回归**

Run: `python -m pytest -v`
Expected: 全部 PASS

- [ ] **Step 8: 提交**

```bash
git add config/minesweeper.json examples/04_minesweeper_agent.py src/agent_frame/desktop/minesweeper.py src/agent_frame/desktop/__init__.py tests/test_minesweeper_build.py
git commit -m "feat: assemble minesweeper vision agent config and example"
```

---

## Task 12: 更新 README 与模块地图

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 README 的运行示例后追加扫雷示例说明**

在 `README.md` 的「快速开始」代码块中，第 4 步之后追加：

```bash
# 5. 扫雷视觉 Agent（多模态计算机使用，需先校准 config/minesweeper.json）
#    Windows；安装桌面依赖：pip install -e ".[desktop]"
MODEL=deepseek-flash python examples/04_minesweeper_agent.py
```

- [ ] **Step 2: 在模块地图表格中追加 desktop 行**

在 `README.md` 的「模块地图」表格最后一行（`server` 行）之后追加：

```
| `desktop` | 桌面自动化：截屏/鼠标控制/棋盘几何/网格标注 + 扫雷工具集 | ✅ 实现 |
```

- [ ] **Step 3: 提交**

```bash
git add README.md
git commit -m "docs: document minesweeper vision agent example"
```

---

## 人工验收（实现完成后，需真机运行）

1. `python -m pytest -v` 全绿，且不依赖真实屏幕/API。
2. 准备一台 Windows、打开目标扫雷、量出一张截图的几何参数，填进 `config/minesweeper.json`。
3. 运行 `MODEL=deepseek-flash python examples/04_minesweeper_agent.py`，观察：
   - 每轮日志里能看到带图的请求（`LOG_LEVEL=DEBUG`）。
   - 鼠标真实点击棋盘格；点击位置与模型给的行列号一致。
   - 本局结束后模型调用 `restart_game` 重开。
4. 若几何偏移导致点偏，微调 `origin_x/origin_y/cell_w/cell_h` 后再试。

---

## 自查（写计划者已核对）

- **Spec 覆盖**：多模态消息（Task 2/3）、Observer 钩子（Task 4）、`desktop` 五文件（Task 5-9）、工具集（Task 10）、配置/依赖/示例（Task 1/11）、README（Task 12）、测试（贯穿各任务）、DPI（Task 7）、重开（Task 10）、图片下采样与 detail（Task 9）、验收（人工验收节）。均有对应任务。
- **占位符**：无 TODO/TBD；`config/minesweeper.json` 的数值是**明确标注需校准的示例值**，非计划占位。
- **类型一致性**：`cell_center(row, col)`、`MouseController.click/move_to/press`、`Message.user_with_image(text, png, *, detail)`、`BoardObserver.observe() -> Message`、`build_registry(config, mouse)`、`build_agent(config, llm, *, mouse, capture)` 在各任务间一致。
