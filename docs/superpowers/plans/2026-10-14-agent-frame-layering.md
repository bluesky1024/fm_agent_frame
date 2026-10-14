# Agent 框架分层重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `fm_agent_frame` 重构成「框架 / 通用能力 / 应用」三层：框架包 `src/agent_frame/` 内不再出现任何扫雷概念，扫雷整体收进 `apps/minesweeper/`，`Observer` 协议换成按模态分开的 `TextSource` / `ImageSource`。

**Architecture:** 框架定义「本轮输入源」两个正交协议（`TextSource` 产出文本、`ImageSource` 产出 PNG 并可持有 `caption: TextSource` 作为图的描述），由纯函数 `build_turn_messages` 组装成临时附加的 user 消息；通用计算机使用能力（截屏 / 输入 / 屏幕图源）收在 `computer/`，零领域知识；扫雷的全部领域代码（游戏、几何、标注、提示词、工具、组装）收在 `apps/minesweeper/`。

**Tech Stack:** Python 3.12、pydantic v2、`typing.Protocol`、asyncio、pytest + pytest-asyncio（`asyncio_mode = "auto"`）、Pillow / mss / pyautogui（桌面依赖）

**Spec:** `docs/superpowers/specs/2026-10-14-agent-frame-layering-design.md`

## Global Constraints

- Python ≥ 3.12；运行测试用 `pytest`（仓库根目录），配置已在 `pyproject.toml`（`pythonpath = ["src", "."]`）。
- **依赖方向硬约束**：`apps/*` 可以 import `agent_frame.*`；`agent_frame.*`（含 `computer`）**任何情况下不得 import `apps.*`**。任何中间状态也不例外。
- 验收基线：`grep -rn "minesweeper\|扫雷\|BoardGeometry\|GridAnnotator" src/agent_frame/` 输出为空。
- 每个任务的测试**不得依赖真实 API 与真实屏幕**：LLM 用 fake provider，截屏用注入的 `grabber`，鼠标用注入的 `FakeBackend`。
- 移动文件一律用 `git mv` 保留历史；重命名测试文件同样用 `git mv`。
- 系统提示词（`SYSTEM_PROMPT`）与图像说明（`CAPTION`）的**文字内容不变**，只改存放位置。
- 13 模块骨架（`memory` / `prompt` / `obs` / `retrieval` / `multi_agent` / `eval` / `server` / `llm` / `tools` / `agent` / `messages` / `config` / `errors`）保持原样，只改 `desktop` 的去向与 `agent` 的输入抽象。
- 每个任务结束时 `pytest` 必须全绿，然后提交。

## Review Focus

设计文档是愿景文档，不会枚举所有输入。以下几类最可能让使用者踩坑，每条都已钉到对应任务的测试里：

| # | 输入 / 条件 | 合理预期 | 钉在 |
|---|---|---|---|
| 1 | `inputs` 里混进既非 `TextSource` 也非 `ImageSource` 的对象（参数拼错） | 该源降级为「本轮输入不可用」消息，循环继续；**不是** AttributeError 中断整个 run | Task 3 |
| 2 | `inputs` 为空（纯文本 Agent） | 行为与重构前逐字节一致：不附加任何消息，`steps` 与最终输出不变 | Task 5 |
| 3 | 某个源、或它的 `caption` 抛异常（截屏失败 / 标注炸了） | 只有该源降级，其余源照常产出，Agent 不崩 | Task 3 |
| 4 | 无 caption 的图片消息 | `content` 数组只含 `image_url`；`_to_openai_messages` 产出合法 OpenAI 载荷 | Task 3 |
| 5 | 同一轮声明多个源 | 产出消息顺序与声明顺序一致（顺序影响模型注意力） | Task 3 |

## 批次顺序说明（与 spec §8 的差异）

Spec §8 的批次顺序为「分出应用 → 通用能力归位 → 协议替换」。实施时把**前两批对调**：先「通用能力归位」（纯机械搬家），再「协议替换」，最后「分出应用」。

原因：`GridAnnotator` 只有在 `BoardObserver` 停止引用它之后才能离开框架包，而删掉 `BoardObserver` 正是「协议替换」这一步。若先「分出应用」，`src/agent_frame/desktop/observer.py` 会短暂 import `apps.minesweeper.grid`，直接违反依赖方向硬约束。

Phase C 内部也有顺序要求：**先把应用组装（`build.py` / `prompts.py`）搬出去**，再逐个搬剩下的应用文件。因为 `apps/*` → `agent_frame.*` 是允许方向，先搬组装就不会出现「框架包 import apps」的中间态。

---

## Phase A：通用能力归位（`desktop/` 的通用部分 → `computer/`）

### Task 1: 截屏能力搬入 `computer/`

**Files:**
- Create: `src/agent_frame/computer/__init__.py`
- Move: `src/agent_frame/desktop/screen.py` → `src/agent_frame/computer/screen.py`
- Modify: `src/agent_frame/desktop/observer.py:11`、`src/agent_frame/desktop/minesweeper.py:9`、`src/agent_frame/desktop/__init__.py`
- Move test: `tests/test_desktop_screen.py` → `tests/test_computer_screen.py`

**Interfaces:**
- Consumes: 无
- Produces: `agent_frame.computer.screen.CaptureRegion`（pydantic 模型：`left/top/width/height`）、`agent_frame.computer.screen.ScreenCapture`（`__init__(region, grabber=None, *, scale=None)`、`.region`、`.grab() -> PIL.Image`）

- [ ] **Step 1: 移动源文件与测试文件**

```bash
mkdir -p src/agent_frame/computer
git mv src/agent_frame/desktop/screen.py src/agent_frame/computer/screen.py
git mv tests/test_desktop_screen.py tests/test_computer_screen.py
```

- [ ] **Step 2: 新建包入口**

`src/agent_frame/computer/__init__.py`：

```python
"""通用计算机使用能力：截屏、鼠标/键盘输入、把屏幕变成一次请求的图片输入。

与领域无关：不知道棋盘、网格等任何应用概念。
"""

from agent_frame.computer.screen import CaptureRegion, ScreenCapture

__all__ = ["CaptureRegion", "ScreenCapture"]
```

- [ ] **Step 3: 更新引用处**

`src/agent_frame/desktop/observer.py` 第 11 行：

```python
from agent_frame.computer.screen import ScreenCapture
```

`src/agent_frame/desktop/minesweeper.py` 第 9 行：

```python
from agent_frame.computer.screen import CaptureRegion, ScreenCapture
```

`tests/test_computer_screen.py` 第 3 行：

```python
from agent_frame.computer.screen import CaptureRegion, ScreenCapture
```

- [ ] **Step 4: 把 `desktop/__init__.py` 收敛为纯 docstring**

没有任何模块 import `agent_frame.desktop` 包本身（已用 `grep -rn "from agent_frame.desktop import"` 确认无结果），只 import 其子模块。把 `src/agent_frame/desktop/__init__.py` 全部内容替换为：

```python
"""桌面相关模块（正在逐步迁出：通用部分 → agent_frame.computer，应用部分 → apps/）。"""
```

这样后续任务不必反复维护它的 re-export。

- [ ] **Step 5: 跑测试**

Run: `pytest -q`
Expected: 全部通过（65 passed）

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: 截屏能力迁入 agent_frame.computer

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

### Task 2: 输入能力搬入 `computer/`

**Files:**
- Move: `src/agent_frame/desktop/mouse.py` → `src/agent_frame/computer/input.py`（类 `MouseController` → `InputController`）
- Modify: `src/agent_frame/computer/__init__.py`、`src/agent_frame/desktop/minesweeper.py`、`src/agent_frame/tools/desktop/click_cell.py`、`src/agent_frame/tools/desktop/flag_cell.py`、`src/agent_frame/tools/desktop/restart_game.py`、`examples/04_minesweeper_autoplay.py:24`
- Move test: `tests/test_desktop_mouse.py` → `tests/test_computer_input.py`
- Modify test: `tests/test_desktop_tools.py:4`、`tests/test_minesweeper_build.py:4`

**Interfaces:**
- Consumes: 无
- Produces: `agent_frame.computer.input.InputController`（`__init__(backend=None)`、`click(x, y, *, button="left")`、`move_to(x, y)`、`press(key)`、`shift_click(x, y, *, button="left")`）、`agent_frame.computer.input.enable_dpi_awareness()`

改名理由：该类除 `click` / `move_to` 外还有 `press(key)`（键盘），叫 Mouse 名不副实。

- [ ] **Step 1: 移动文件并改名**

```bash
git mv src/agent_frame/desktop/mouse.py src/agent_frame/computer/input.py
git mv tests/test_desktop_mouse.py tests/test_computer_input.py
```

- [ ] **Step 2: 在 `input.py` 内把类名与 docstring 里的 `MouseController` 全部替换为 `InputController`**

```bash
sed -i '' 's/MouseController/InputController/g' src/agent_frame/computer/input.py
```

（Linux 上把 `sed -i ''` 换成 `sed -i`。改完打开文件确认模块 docstring 仍准确。）

- [ ] **Step 3: 更新引用处**

`src/agent_frame/computer/__init__.py` 追加：

```python
from agent_frame.computer.input import InputController, enable_dpi_awareness

__all__ = [
    "CaptureRegion",
    "InputController",
    "ScreenCapture",
    "enable_dpi_awareness",
]
```

把 `src/agent_frame/desktop/minesweeper.py` 第 7 行改为：

```python
from agent_frame.computer.input import InputController
```

并把同文件内的 `MouseController` 全部替换为 `InputController`（2 处：`build_registry` 的参数标注、`build_agent` 里的 `mouse or MouseController()`）。

三个工具文件 `src/agent_frame/tools/desktop/{click_cell,flag_cell,restart_game}.py`：把 import 行改为

```python
from agent_frame.computer.input import InputController
```

并把各自 `__init__` 的参数标注 `MouseController` 改为 `InputController`。

`examples/04_minesweeper_autoplay.py` 第 24 行改为：

```python
from agent_frame.computer.input import enable_dpi_awareness
```

- [ ] **Step 4: 更新测试**

```bash
sed -i '' 's/agent_frame\.desktop\.mouse/agent_frame.computer.input/g; s/MouseController/InputController/g' \
  tests/test_computer_input.py tests/test_desktop_tools.py tests/test_minesweeper_build.py
```

- [ ] **Step 5: 跑测试**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: 输入能力迁入 agent_frame.computer，MouseController 改名 InputController

该类除 click/move_to 外还有 press(key) 键盘操作，Mouse 名不副实。

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

---

## Phase B：输入源协议替换（删 `Observer`）

### Task 3: `agent/inputs.py` 与消息组装

**Files:**
- Create: `src/agent_frame/agent/inputs.py`
- Modify: `src/agent_frame/messages.py:64-76`（`user_with_image`）
- Create test: `tests/test_agent_inputs.py`

**Interfaces:**
- Consumes: `agent_frame.messages.Message`
- Produces:
  - `agent_frame.agent.inputs.TextSource`（runtime_checkable Protocol：`async text() -> str`）
  - `agent_frame.agent.inputs.ImageSource`（runtime_checkable Protocol：属性 `caption: TextSource | None`、`async image() -> bytes`）
  - `agent_frame.agent.inputs.TurnInput = TextSource | ImageSource`
  - `agent_frame.agent.inputs.StaticText(text: str)`（实现 `TextSource`）
  - `agent_frame.agent.inputs.build_turn_messages(sources: Sequence[TurnInput], *, image_detail: str = "high") -> list[Message]`
  - `Message.user_with_image(text: str | None, png: bytes, *, detail: str = "high")`

- [ ] **Step 1: 写失败测试**

`tests/test_agent_inputs.py`：

```python
from agent_frame.agent.inputs import StaticText, build_turn_messages
from agent_frame.messages import Message


class FakeImage:
    """实现 ImageSource 的最小对象。"""

    def __init__(self, png: bytes = b"\x89PNG-fake", caption=None) -> None:
        self.caption = caption
        self._png = png

    async def image(self) -> bytes:
        return self._png


async def test_text_source_becomes_plain_user_message():
    messages = await build_turn_messages([StaticText("现在几点？")])
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "现在几点？"


async def test_image_source_with_caption_puts_both_in_one_message():
    messages = await build_turn_messages([FakeImage(caption=StaticText("这是棋盘"))])
    assert len(messages) == 1
    text_part, image_part = messages[0].content
    assert text_part.type == "text"
    assert text_part.text == "这是棋盘"
    assert image_part.type == "image_url"


async def test_image_source_without_caption_emits_only_image_part():
    """Review Focus #4：无 caption 时 content 数组只剩 image_url。"""
    messages = await build_turn_messages([FakeImage()])
    parts = messages[0].content
    assert len(parts) == 1
    assert parts[0].type == "image_url"


async def test_sources_keep_declaration_order():
    """Review Focus #5：顺序与声明一致。"""
    messages = await build_turn_messages(
        [StaticText("一"), FakeImage(caption=StaticText("二")), StaticText("三")]
    )
    got = [
        m.content if isinstance(m.content, str) else m.content[0].text for m in messages
    ]
    assert got == ["一", "二", "三"]


async def test_failing_source_degrades_without_breaking_others():
    """Review Focus #3：单源异常只降级该源。"""

    class Boom:
        async def text(self) -> str:
            raise RuntimeError("source down")

    messages = await build_turn_messages([Boom(), StaticText("还有我")])
    assert messages[0].content.startswith("[本轮输入不可用")
    assert "source down" in messages[0].content
    assert messages[1].content == "还有我"


async def test_failing_caption_degrades_that_source():
    """Review Focus #3：caption 抛异常同样只降级该源。"""

    class BadCaption:
        async def text(self) -> str:
            raise RuntimeError("caption down")

    messages = await build_turn_messages([FakeImage(caption=BadCaption())])
    assert messages[0].content.startswith("[本轮输入不可用")


async def test_non_conforming_object_degrades_to_unavailable_message():
    """Review Focus #1：既非 TextSource 也非 ImageSource 的对象不应中断整轮。"""
    messages = await build_turn_messages([object()])
    assert messages[0].content.startswith("[本轮输入不可用")


async def test_image_detail_is_applied():
    messages = await build_turn_messages([FakeImage()], image_detail="low")
    assert messages[0].content[0].image_url["detail"] == "low"


def test_user_with_image_without_text_has_only_image_part():
    m = Message.user_with_image(None, b"\x89PNG")
    assert len(m.content) == 1
    assert m.content[0].type == "image_url"


def test_user_with_image_still_works_with_text():
    m = Message.user_with_image("棋盘", b"\x89PNG", detail="low")
    assert m.content[0].text == "棋盘"
    assert m.content[1].image_url["detail"] == "low"


def test_to_openai_messages_supports_image_only_message():
    """Review Focus #4：无 caption 的图片消息要能转成合法 OpenAI 载荷。"""
    from agent_frame.llm.openai_compat import _to_openai_messages

    out = _to_openai_messages([Message.user_with_image(None, b"\x89PNG")])
    assert out[0]["role"] == "user"
    assert out[0]["content"][0]["type"] == "image_url"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_agent_inputs.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_frame.agent.inputs'`

- [ ] **Step 3: 新建 `src/agent_frame/agent/inputs.py`**

```python
"""本轮输入源：把「这一次请求要附带的文本 / 图片」抽成两个独立接口。

与 Memory 的边界：
- Memory 聚合**跨轮持久**的对话历史，会被 save / load；
- 本模块的输入源只产出**只活在这一次请求里**的内容（截图每轮都换），
  每轮调用一次，产物永不进入永久历史。
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from agent_frame.messages import Message


@runtime_checkable
class TextSource(Protocol):
    """文本输入源：产出一段文本。"""

    async def text(self) -> str: ...


@runtime_checkable
class ImageSource(Protocol):
    """图片输入源：产出一张 PNG，并可选地携带「描述这张图」的文本源。

    caption 是关联点：它指向的 TextSource 会与这张图进入**同一条**消息，
    文本在前、图片紧随其后，使模型把该文本读作这张图的说明。
    """

    caption: TextSource | None

    async def image(self) -> bytes: ...


TurnInput = TextSource | ImageSource


class StaticText:
    """最简单的文本源：固定文本。

    既可用作独立的文本说明，也可用作某张图的 caption（接口独立 ≠ 不能组合）。
    """

    def __init__(self, text: str) -> None:
        self._text = text

    async def text(self) -> str:
        return self._text


async def build_turn_messages(
    sources: Sequence[TurnInput], *, image_detail: str = "high"
) -> list[Message]:
    """把本轮输入源组装成消息列表（有序，逐源一条消息）。

    - TextSource  → ``Message.user(text)``
    - ImageSource → ``Message.user_with_image(caption?, png, detail=image_detail)``；
      caption 与图片同处一条消息，无 caption 时产出只含 ImagePart 的消息。

    单个源出错不中断：该源产出一条「本轮输入不可用」的文本消息供模型知情，
    其余源照常产出。
    """
    results = await asyncio.gather(
        *(_build_one(src, image_detail) for src in sources), return_exceptions=True
    )
    messages: list[Message] = []
    for result in results:
        if isinstance(result, BaseException):
            messages.append(Message.user(f"[本轮输入不可用：{result}]"))
        else:
            messages.append(result)
    return messages


async def _build_one(src: TurnInput, image_detail: str) -> Message:
    if isinstance(src, ImageSource):
        png = await src.image()
        caption = await src.caption.text() if src.caption is not None else None
        return Message.user_with_image(caption, png, detail=image_detail)
    return Message.user(await src.text())
```

- [ ] **Step 4: 放宽 `Message.user_with_image`**

把 `src/agent_frame/messages.py` 的 `user_with_image` 整个方法替换为：

```python
    @classmethod
    def user_with_image(
        cls, text: str | None, png: bytes, *, detail: str = "high"
    ) -> "Message":
        """构造一条「可选文本 + 内联 PNG 图片」的 user 消息（base64 data URL）。

        text 为 None 时不产出 TextPart，只留 ImagePart（OpenAI 协议允许）。
        """
        parts: list[ContentPart] = []
        if text is not None:
            parts.append(TextPart(text=text))
        data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        parts.append(ImagePart(image_url={"url": data_url, "detail": detail}))
        return cls(role="user", content=parts)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest -q`
Expected: 全部通过（含新增的 11 项）

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat: 新增本轮输入源协议 TextSource / ImageSource 与消息组装

按模态拆成两个正交协议，图片源通过 caption 结构性绑定其描述文本，
二者进入同一条消息；单源失败降级为提示消息，不中断循环。

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

### Task 4: `computer/sources.py` —— 屏幕图源

**Files:**
- Create: `src/agent_frame/computer/sources.py`
- Modify: `src/agent_frame/computer/__init__.py`
- Create test: `tests/test_computer_sources.py`

**Interfaces:**
- Consumes: `agent_frame.agent.inputs.TextSource`、`agent_frame.computer.screen.ScreenCapture`、PIL
- Produces:
  - `agent_frame.computer.sources.Annotator`（Protocol：`draw(img: Image.Image) -> Image.Image`）
  - `agent_frame.computer.sources.ScreenImageSource(capture, *, annotator=None, caption=None, max_px=1300)`，属性 `caption`，方法 `async image() -> bytes`

- [ ] **Step 1: 写失败测试**

`tests/test_computer_sources.py`：

```python
import io

from PIL import Image

from agent_frame.agent.inputs import StaticText
from agent_frame.computer.screen import CaptureRegion, ScreenCapture
from agent_frame.computer.sources import ScreenImageSource


def _capture(w: int = 40, h: int = 30) -> ScreenCapture:
    region = CaptureRegion(left=0, top=0, width=w, height=h)
    return ScreenCapture(
        region, grabber=lambda r: Image.new("RGB", (r.width, r.height), "white")
    )


async def test_image_returns_png_of_capture_size():
    src = ScreenImageSource(_capture(40, 30))
    png = await src.image()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert Image.open(io.BytesIO(png)).size == (40, 30)


async def test_annotator_is_applied():
    class Red:
        def draw(self, img):
            return Image.new("RGB", img.size, "red")

    src = ScreenImageSource(_capture(), annotator=Red())
    img = Image.open(io.BytesIO(await src.image()))
    assert img.getpixel((0, 0)) == (255, 0, 0)


async def test_max_px_downscales_largest_side():
    src = ScreenImageSource(_capture(400, 200), max_px=100)
    img = Image.open(io.BytesIO(await src.image()))
    assert img.size == (100, 50)


async def test_no_annotator_returns_unmodified_frame():
    src = ScreenImageSource(_capture())
    img = Image.open(io.BytesIO(await src.image()))
    assert img.getpixel((0, 0)) == (255, 255, 255)


def test_caption_is_passed_through():
    caption = StaticText("这是棋盘")
    src = ScreenImageSource(_capture(), caption=caption)
    assert src.caption is caption


def test_caption_defaults_to_none():
    assert ScreenImageSource(_capture()).caption is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_computer_sources.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_frame.computer.sources'`

- [ ] **Step 3: 新建 `src/agent_frame/computer/sources.py`**

```python
"""把屏幕变成一次请求的图片输入（实现 ImageSource）。

通用能力：截屏 → 可选叠加标注 → 下采样 → PNG。不感知任何应用领域概念，
要叠加什么内容由传入的 Annotator 决定。
"""

from __future__ import annotations

import io
from typing import Protocol

from PIL import Image

from agent_frame.agent.inputs import TextSource
from agent_frame.computer.screen import ScreenCapture


class Annotator(Protocol):
    """在截屏图像上叠加内容。

    实现方拿到的坐标应是「图像坐标系」（即已按截屏区域左上角平移过）。
    """

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
    ) -> None:
        self._capture = capture
        self._annotator = annotator
        self.caption = caption
        self._max_px = max_px

    async def image(self) -> bytes:
        img = self._capture.grab()
        if self._annotator is not None:
            img = self._annotator.draw(img)
        img = _downscale(img, self._max_px)
        return _to_png(img)


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

- [ ] **Step 4: 更新包入口**

`src/agent_frame/computer/__init__.py`：

```python
"""通用计算机使用能力：截屏、鼠标/键盘输入、把屏幕变成一次请求的图片输入。

与领域无关：不知道棋盘、网格等任何应用概念。
"""

from agent_frame.computer.input import InputController, enable_dpi_awareness
from agent_frame.computer.screen import CaptureRegion, ScreenCapture
from agent_frame.computer.sources import Annotator, ScreenImageSource

__all__ = [
    "Annotator",
    "CaptureRegion",
    "InputController",
    "ScreenCapture",
    "ScreenImageSource",
    "enable_dpi_awareness",
]
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat: 新增 computer.ScreenImageSource，屏幕截图成为可复用的图片输入源

只依赖 Annotator 协议，不感知任何具体应用要叠加什么。

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

### Task 5: `ToolUseAgent` 改收 `inputs`，删除 `Observer` 与 `BoardObserver`

**Files:**
- Modify: `src/agent_frame/agent/base.py`（删 `Observer`）、`src/agent_frame/agent/tool_use.py`、`src/agent_frame/agent/__init__.py`、`src/agent_frame/desktop/minesweeper.py`
- Delete: `src/agent_frame/desktop/observer.py`
- Move test: `tests/test_observer_loop.py` → `tests/test_agent_turn_inputs.py`
- Delete test: `tests/test_desktop_observer.py`（价值并入 `tests/test_computer_sources.py` 与 `tests/test_minesweeper_game.py`）
- Modify test: `tests/test_minesweeper_game.py:87-107`

**Interfaces:**
- Consumes: `agent_frame.agent.inputs.TurnInput` / `build_turn_messages`
- Produces: `ToolUseAgent(llm, tools, *, system_prompt=None, max_steps=8, inputs: Sequence[TurnInput] = (), image_detail: str = "high")`

- [ ] **Step 1: 写失败测试**

```bash
git mv tests/test_observer_loop.py tests/test_agent_turn_inputs.py
```

把 `tests/test_agent_turn_inputs.py` 整文件替换为：

```python
from agent_frame.agent import ToolUseAgent
from agent_frame.llm.base import ChatResult
from agent_frame.messages import ToolCall
from agent_frame.tools import ToolRegistry
from agent_frame.tools.builtin import CalculatorTool


class RecordingText:
    """实现 TextSource：每次被取都递增计数。"""

    def __init__(self) -> None:
        self.count = 0

    async def text(self) -> str:
        self.count += 1
        return f"frame-{self.count}"


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


async def test_turn_input_is_refreshed_every_round():
    llm = OneToolThenTextLLM()
    src = RecordingText()
    agent = ToolUseAgent(llm, ToolRegistry([CalculatorTool()]), inputs=[src])

    await agent.run("play")

    # 每轮请求前各取一次：首轮 + 工具执行后的下一轮
    assert src.count == 2
    # 第一次请求：历史末尾是本轮输入
    assert llm.calls[0][-1].content == "frame-1"
    # 第二次请求：末尾是最新一帧；旧帧不再出现
    second = [m.content for m in llm.calls[1]]
    assert second[-1] == "frame-2"
    assert "frame-1" not in second


async def test_history_keeps_text_but_no_old_turn_input():
    llm = OneToolThenTextLLM()
    src = RecordingText()
    agent = ToolUseAgent(llm, ToolRegistry([CalculatorTool()]), inputs=[src])

    await agent.run("play")

    # 文本进展（assistant 工具调用 + 工具结果）保留在历史里
    second_roles = [m.role for m in llm.calls[1]]
    assert "tool" in second_roles
    # 历史里最多只有一帧（当前帧），不随轮数累积
    frame_count = sum(1 for m in llm.calls[1] if str(m.content).startswith("frame-"))
    assert frame_count == 1


async def test_no_inputs_keeps_default_behavior():
    """Review Focus #2：纯文本 Agent 行为不变。"""
    llm = OneToolThenTextLLM()
    agent = ToolUseAgent(llm, ToolRegistry([CalculatorTool()]))

    result = await agent.run("hi")

    assert result.output == "done"
    assert len(result.steps) == 2
    # 未装配输入源时，请求里不应多出任何消息
    assert [m.content for m in llm.calls[-1]] == [
        "hi",
        None,  # assistant 的 tool_calls 消息，content 为 None
        "ok",
    ]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_agent_turn_inputs.py -q`
Expected: FAIL — `TypeError: ToolUseAgent.__init__() got an unexpected keyword argument 'inputs'`

- [ ] **Step 3: 删除 `Observer` 协议**

`src/agent_frame/agent/base.py`：删掉文件末尾的 `Observer` 类（第 40-46 行）以及不再使用的 `Message` import，只保留 `AgentStep` / `AgentResult` / `Agent`。

- [ ] **Step 4: 改写 `src/agent_frame/agent/tool_use.py`**

```python
"""ToolUseAgent：ReAct 风格的「思考 → 调工具 → 观察 → 再思考」循环。

这是整个框架的核心机制：LLM 不直接给出最终答案，
而是先决定「要不要调用工具」，循环直到它给出纯文本回答为止。

可选装配本轮输入源（TextSource / ImageSource）：每轮请求前各取一次，产出
「本轮输入」消息临时附在请求末尾（通常是带图的 user 消息），支持
「看 → 做 → 再看」的多模态场景。

本轮输入**不进永久对话历史**：发给 LLM 的永远是「完整文本历史 + 本轮输入」，
历史里的旧截图不会被反复重发，请求体不随轮数膨胀。
"""

from __future__ import annotations

from collections.abc import Sequence

from agent_frame.agent.base import AgentResult, AgentStep
from agent_frame.agent.inputs import TurnInput, build_turn_messages
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
        inputs: Sequence[TurnInput] = (),
        image_detail: str = "high",
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._system_prompt = system_prompt
        self._max_steps = max_steps
        self._inputs = list(inputs)
        self._image_detail = image_detail

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

        tool_specs = self._tools.to_tool_specs()
        steps: list[AgentStep] = []

        for index in range(self._max_steps):
            # 本轮输入每轮重新产出，临时附加，永不进入永久历史
            turn = await build_turn_messages(
                self._inputs, image_detail=self._image_detail
            )
            result = await self._llm.chat(messages + turn, tool_specs)

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

- [ ] **Step 5: 更新 `src/agent_frame/agent/__init__.py`**

```python
from agent_frame.agent.base import Agent, AgentResult, AgentStep
from agent_frame.agent.inputs import (
    ImageSource,
    StaticText,
    TextSource,
    TurnInput,
    build_turn_messages,
)
from agent_frame.agent.tool_use import ToolUseAgent

__all__ = [
    "Agent",
    "AgentResult",
    "AgentStep",
    "ImageSource",
    "StaticText",
    "TextSource",
    "ToolUseAgent",
    "TurnInput",
    "build_turn_messages",
]
```

- [ ] **Step 6: 删掉 `BoardObserver`，改写 `desktop/minesweeper.py` 的组装**

```bash
git rm src/agent_frame/desktop/observer.py
git rm tests/test_desktop_observer.py
```

把 `src/agent_frame/desktop/minesweeper.py` 的 import 段换成：

```python
from agent_frame.agent import ToolUseAgent
from agent_frame.agent.inputs import StaticText
from agent_frame.computer.input import InputController
from agent_frame.computer.screen import CaptureRegion, ScreenCapture
from agent_frame.computer.sources import ScreenImageSource
from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.tools import ToolRegistry
from agent_frame.tools.desktop import ClickCellTool, FlagCellTool, RestartGameTool
```

在 `SYSTEM_PROMPT` 之后新增：

```python
CAPTION = (
    "这是当前扫雷棋盘的截图，每个格子外侧已标注 1 基行列号。"
    "请根据棋盘状态决定下一步动作。"
)
```

`build_agent` 换成：

```python
def build_agent(
    config: dict,
    llm,
    *,
    mouse: InputController | None = None,
    capture: ScreenCapture | None = None,
) -> ToolUseAgent:
    geometry = BoardGeometry(**config["geometry"])
    region = CaptureRegion(**config["region"])
    controller = mouse or InputController()
    capture = capture or ScreenCapture(region)
    # 棋盘几何在屏幕坐标系；标注画在图像坐标系 → 按截屏区域左上角平移
    source = ScreenImageSource(
        capture,
        annotator=GridAnnotator(geometry.translated(-region.left, -region.top)),
        caption=StaticText(CAPTION),
        max_px=config.get("image_max_px", 1300),
    )
    registry = build_registry(config, controller)
    return ToolUseAgent(
        llm,
        registry,
        system_prompt=SYSTEM_PROMPT,
        max_steps=config.get("max_steps", 300),
        inputs=[source],
        image_detail=config.get("image_detail", "high"),
    )
```

（`build_registry` 只把参数标注的 `MouseController` 换成 `InputController`，函数体不变。）

- [ ] **Step 7: 改写 `tests/test_minesweeper_game.py` 的标注可见性测试**

把 `test_annotated_frame_contains_row_col_labels`（第 87-107 行）整个替换为：

```python
async def test_annotated_frame_contains_row_col_labels():
    from agent_frame.agent.inputs import StaticText, build_turn_messages
    from agent_frame.computer.screen import CaptureRegion, ScreenCapture
    from agent_frame.computer.sources import ScreenImageSource
    from agent_frame.desktop.annotate import GridAnnotator
    from agent_frame.desktop.geometry import BoardGeometry

    cfg = board_config()
    geometry = BoardGeometry(**cfg["geometry"])
    region = CaptureRegion(**cfg["region"])
    capture = ScreenCapture(
        region, grabber=lambda r: Image.new("RGB", (r.width, r.height), "white")
    )
    # 组装方式与 apps 侧一致：几何按截屏区域左上角平移后再画
    source = ScreenImageSource(
        capture,
        annotator=GridAnnotator(geometry.translated(-region.left, -region.top)),
        caption=StaticText("棋盘"),
    )
    [message] = await build_turn_messages([source])

    data_url = message.content[1].image_url["url"]
    png = base64.b64decode(data_url.split(",", 1)[1])
    img = Image.open(io.BytesIO(png)).convert("RGB")
    # 蓝色行列标尺应出现在图内（抗锯齿，用偏蓝判据）
    bluish = sum(
        1 for (r, g, b) in img.getdata() if b > 80 and b > r + 30 and b > g + 30
    )
    assert bluish > 0
```

- [ ] **Step 8: 跑测试确认通过**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 9: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: 删除 Observer 协议，ToolUseAgent 改收本轮输入源列表

循环里不再有视觉分支：不装配输入源即纯文本模式。
BoardObserver 的职责拆到 ScreenImageSource（computer 层）与
GridAnnotator（应用层）。

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

---

## Phase C：分出应用（`apps/minesweeper/`）

### Task 6: 扫雷组装迁入 `apps/`，删除框架内的组装代码

**Files:**
- Create: `apps/__init__.py`、`apps/minesweeper/__init__.py`、`apps/minesweeper/prompts.py`、`apps/minesweeper/build.py`
- Delete: `src/agent_frame/desktop/minesweeper.py`
- Modify: `tests/test_minesweeper_build.py`、`examples/04_minesweeper_autoplay.py`

**Interfaces:**
- Consumes: `agent_frame.agent.{ToolUseAgent}`、`agent_frame.agent.inputs.StaticText`、`agent_frame.computer.{InputController, CaptureRegion, ScreenCapture, ScreenImageSource}`、`agent_frame.desktop.annotate.GridAnnotator` 与 `agent_frame.desktop.geometry.BoardGeometry`（仍在框架内，Phase C 稍后搬到 `apps/`）、`agent_frame.tools.ToolRegistry`、`agent_frame.tools.desktop.{ClickCellTool, FlagCellTool, RestartGameTool}`（同上）
- Produces: `apps.minesweeper.prompts.{SYSTEM_PROMPT, CAPTION}`、`apps.minesweeper.build.{build_registry, build_agent}`

先搬组装的理由：`apps/*` → `agent_frame.*` 是允许方向，所以这一步之后 `apps/minesweeper/build.py` 可以自由引用仍在框架内的 `annotate` / `geometry` / `tools.desktop`，而框架包内不会出现任何 `import apps`。

- [ ] **Step 1: 建目录**

```bash
mkdir -p apps/minesweeper
```

`apps/__init__.py`：

```python
"""示例应用：用框架的通用能力搭出来的具体 Agent 应用。"""
```

`apps/minesweeper/__init__.py`：

```python
"""扫雷应用：游戏本体、棋盘几何、网格标注、提示词、工具与组装。"""
```

- [ ] **Step 2: 新建 `apps/minesweeper/prompts.py`**

先打开 `src/agent_frame/desktop/minesweeper.py`，把其中的 `SYSTEM_PROMPT` 常量与 `CAPTION` 常量**逐字符原样**搬进新文件：

```python
"""扫雷 Agent 的提示词：系统提示词与截图说明。"""

SYSTEM_PROMPT = """你是一个扫雷专家，通过截图观察棋盘并操作鼠标通关。

每轮你会收到一张最新棋盘截图，格子外侧标注了 1 基行列号（行自上而下、列自左而右）。
棋盘上：数字表示该格周围 8 格的雷数；空白表示周围无雷；旗子表示你标记的雷。

可用工具：
- click_cell(row, col)：翻开一个格子（确定它安全时）。
- flag_cell(row, col)：给一个格子插旗（确定它是雷时）。
- restart_game()：仅当本局已结束（胜利，或已踩到雷）时调用，重开新局。

规则：
- 每轮把当前所有能确定的动作一次性做完：确定的雷全部 flag_cell，确定安全的格子全部 click_cell。
- 不要一轮只做一个动作；也不要把本可确定的动作留到下一轮。
- 只依据最新截图决策，不要重复操作已经翻开的格子。
- 直接调用工具，不要输出任何解释、推理或思考过程。
- 无法确定时，选择最可能安全的格子翻开（不要乱猜高风险格）。
- 本局结束时必须调用 restart_game 开新局，继续游戏。"""

CAPTION = (
    "这是当前扫雷棋盘的截图，每个格子外侧已标注 1 基行列号。"
    "请根据棋盘状态决定下一步动作。"
)
```

- [ ] **Step 3: 新建 `apps/minesweeper/build.py`**

```python
"""扫雷 Agent 的组装：工具注册与 Agent 构建。"""

from __future__ import annotations

from agent_frame.agent import ToolUseAgent
from agent_frame.agent.inputs import StaticText
from agent_frame.computer.input import InputController
from agent_frame.computer.screen import CaptureRegion, ScreenCapture
from agent_frame.computer.sources import ScreenImageSource
from agent_frame.desktop.annotate import GridAnnotator
from agent_frame.desktop.geometry import BoardGeometry
from agent_frame.tools import ToolRegistry
from agent_frame.tools.desktop import ClickCellTool, FlagCellTool, RestartGameTool
from apps.minesweeper.prompts import CAPTION, SYSTEM_PROMPT


def build_registry(config: dict, controller: InputController) -> ToolRegistry:
    geometry = BoardGeometry(**config["geometry"])
    restart = config["restart"]
    if restart["type"] == "click":
        restart_tool = RestartGameTool(controller, click_xy=(restart["x"], restart["y"]))
    else:
        restart_tool = RestartGameTool(controller, key=restart["key"])
    return ToolRegistry(
        [
            ClickCellTool(geometry, controller),
            FlagCellTool(geometry, controller),
            restart_tool,
        ]
    )


def build_agent(
    config: dict,
    llm,
    *,
    mouse: InputController | None = None,
    capture: ScreenCapture | None = None,
) -> ToolUseAgent:
    geometry = BoardGeometry(**config["geometry"])
    region = CaptureRegion(**config["region"])
    controller = mouse or InputController()
    capture = capture or ScreenCapture(region)
    # 棋盘几何在屏幕坐标系；标注画在图像坐标系 → 按截屏区域左上角平移
    source = ScreenImageSource(
        capture,
        annotator=GridAnnotator(geometry.translated(-region.left, -region.top)),
        caption=StaticText(CAPTION),
        max_px=config.get("image_max_px", 1300),
    )
    registry = build_registry(config, controller)
    return ToolUseAgent(
        llm,
        registry,
        system_prompt=SYSTEM_PROMPT,
        max_steps=config.get("max_steps", 300),
        inputs=[source],
        image_detail=config.get("image_detail", "high"),
    )
```

- [ ] **Step 4: 删除框架内的组装文件**

```bash
git rm src/agent_frame/desktop/minesweeper.py
```

- [ ] **Step 5: 更新测试**

`tests/test_minesweeper_build.py` 顶部 import 段替换为：

```python
from PIL import Image

from agent_frame.computer.input import InputController
from agent_frame.computer.screen import CaptureRegion, ScreenCapture
from apps.minesweeper.build import build_agent, build_registry
```

（`_config()` 的内容不变；文件内已是 `InputController`，Task 2 时已替换。）

- [ ] **Step 6: 更新入口 `examples/04_minesweeper_autoplay.py`**

```python
from agent_frame.config import get_settings
from agent_frame.computer.input import enable_dpi_awareness
from agent_frame.llm import OpenAICompatProvider
from agent_frame.obs import setup_logging

# apps/ 与 games/ 都不在已安装的包里（打包只收 src/）：直接运行本脚本时把仓库根加入 sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.minesweeper.build import build_agent  # noqa: E402  需先补 sys.path
from games.minesweeper import board_config  # noqa: E402  需先补 sys.path（Task 7 后改为 apps.minesweeper.game）
```

`main()` 与 `build_config()` 保持原样（只依赖上面两个名字，签名未变）。模块 docstring 里描述组装来源的句子改为指向 `apps/minesweeper/build.py`。

- [ ] **Step 7: 跑测试**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: 扫雷 Agent 组装与提示词迁入 apps/minesweeper

框架包里不再有扫雷的提示词与组装代码。

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

### Task 7: 扫雷游戏本体搬入 `apps/`

**Files:**
- Move: `games/minesweeper.py` → `apps/minesweeper/game.py`
- Delete: `games/__init__.py`
- Modify: `tests/test_minesweeper_game.py:6`、`examples/04_minesweeper_autoplay.py`

**Interfaces:**
- Consumes: 无
- Produces: `apps.minesweeper.game`（常量 `CELL/HEADER/ROWS/COLS/MINES/GAME_ORIGIN_X/GAME_ORIGIN_Y/LABEL_MARGIN_X/LABEL_MARGIN_Y`、`MinesweeperBoard`、`MinesweeperGUI`、`board_config()`）

- [ ] **Step 1: 移动**

```bash
git mv games/minesweeper.py apps/minesweeper/game.py
git rm games/__init__.py
```

- [ ] **Step 2: 更新引用处**

`tests/test_minesweeper_game.py` 顶部 import 段：

```python
from apps.minesweeper.game import (
```

`examples/04_minesweeper_autoplay.py`：

```python
from apps.minesweeper.game import board_config  # noqa: E402  需先补 sys.path

GAME_PATH = _REPO_ROOT / "apps" / "minesweeper" / "game.py"
```

（删掉 Task 6 Step 6 里那条临时注释。）模块 docstring 第 3 行里的 `games/minesweeper.py` 改成 `apps/minesweeper/game.py`。

- [ ] **Step 3: 跑测试**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: 扫雷游戏本体从 games/ 迁入 apps/minesweeper/game.py

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

### Task 8: `GridAnnotator` 搬入 `apps/`

**Files:**
- Move: `src/agent_frame/desktop/annotate.py` → `apps/minesweeper/grid.py`
- Move test: `tests/test_desktop_annotate.py` → `tests/test_minesweeper_grid.py`
- Modify: `apps/minesweeper/build.py`、`tests/test_minesweeper_game.py`

**Interfaces:**
- Consumes: `agent_frame.desktop.geometry.BoardGeometry`（本任务时仍在框架内，Task 9 一并迁出）
- Produces: `apps.minesweeper.grid.GridAnnotator(geometry)`，方法 `draw(img: Image.Image) -> Image.Image`

移动安全性：框架包内已无任何模块引用 `GridAnnotator`（唯一引用者 `desktop/minesweeper.py` 已在 Task 6 删除；`apps/minesweeper/build.py` 是应用侧，方向允许）。

- [ ] **Step 1: 移动**

```bash
git mv src/agent_frame/desktop/annotate.py apps/minesweeper/grid.py
git mv tests/test_desktop_annotate.py tests/test_minesweeper_grid.py
```

- [ ] **Step 2: 更新引用处**

`apps/minesweeper/build.py`：

```python
from apps.minesweeper.grid import GridAnnotator
```

`tests/test_minesweeper_grid.py`：

```python
from apps.minesweeper.grid import GridAnnotator
```

`tests/test_minesweeper_game.py` 的 `test_annotated_frame_contains_row_col_labels` 内：

```python
    from apps.minesweeper.grid import GridAnnotator
```

- [ ] **Step 3: 跑测试**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: GridAnnotator 迁入 apps/minesweeper/grid.py

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

### Task 9: `BoardGeometry` 与棋盘常量搬入 `apps/`

**Files:**
- Move: `src/agent_frame/desktop/geometry.py` → `apps/minesweeper/board.py`
- Move test: `tests/test_desktop_geometry.py` → `tests/test_minesweeper_board.py`
- Modify: `apps/minesweeper/board.py`（加常量与 `board_config`）、`apps/minesweeper/game.py`（移出常量与 `board_config`）、`apps/minesweeper/grid.py`、`apps/minesweeper/build.py`、`src/agent_frame/tools/desktop/click_cell.py`、`src/agent_frame/tools/desktop/flag_cell.py`、`tests/test_desktop_tools.py`、`tests/test_minesweeper_game.py`、`tests/test_minesweeper_grid.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `apps.minesweeper.board`：常量 `CELL=32, HEADER=40, ROWS=9, COLS=9, MINES=5, GAME_ORIGIN_X=200, GAME_ORIGIN_Y=200, LABEL_MARGIN_X=24, LABEL_MARGIN_Y=20`
  - `apps.minesweeper.board.BoardGeometry(origin_x, origin_y, cell_w, cell_h, rows, cols)`，方法 `cell_center(row, col) -> tuple[int, int]`（1 基，越界抛 `ValueError`）、`translated(dx, dy) -> BoardGeometry`
  - `apps.minesweeper.board.board_config() -> dict`（键 `geometry` / `region` / `restart`）

- [ ] **Step 1: 移动**

```bash
git mv src/agent_frame/desktop/geometry.py apps/minesweeper/board.py
git mv tests/test_desktop_geometry.py tests/test_minesweeper_board.py
```

- [ ] **Step 2: 把棋盘常量与 `board_config()` 从 `game.py` 移入 `board.py`**

`apps/minesweeper/board.py` 的模块 docstring 换成：

```python
"""扫雷棋盘的几何：常量、行列 ↔ 屏幕像素换算、以及游戏自报的几何配置。

棋盘左上角格子外沿在屏幕 (GAME_ORIGIN_X, GAME_ORIGIN_Y + HEADER)；
截屏区域在棋盘左/上各留边距，供标注行列标尺（否则标尺会被裁到图外）。
"""
```

在 import 段之后、`class BoardGeometry` 之前插入常量：

```python
CELL = 32
HEADER = 40
ROWS = 9
COLS = 9
MINES = 5
GAME_ORIGIN_X = 200
GAME_ORIGIN_Y = 200
LABEL_MARGIN_X = 24
LABEL_MARGIN_Y = 20
```

在文件末尾追加（从 `game.py` 原样搬来，去掉原 docstring 缩进问题即可）：

```python
def board_config() -> dict:
    """返回 agent config 所需的几何/区域/重开参数（屏幕绝对坐标，1 基）。

    棋盘左上角格子外沿在屏幕 (GAME_ORIGIN_X, GAME_ORIGIN_Y + HEADER)；
    重开按钮中心在屏幕 (GAME_ORIGIN_X + COLS*CELL//2, GAME_ORIGIN_Y + HEADER//2)。
    """
    ox = GAME_ORIGIN_X
    oy = GAME_ORIGIN_Y + HEADER
    return {
        "geometry": {
            "origin_x": ox,
            "origin_y": oy,
            "cell_w": CELL,
            "cell_h": CELL,
            "rows": ROWS,
            "cols": COLS,
        },
        "region": {
            "left": ox - LABEL_MARGIN_X,
            "top": oy - LABEL_MARGIN_Y,
            "width": COLS * CELL + LABEL_MARGIN_X,
            "height": ROWS * CELL + LABEL_MARGIN_Y,
        },
        "restart": {
            "type": "click",
            "x": GAME_ORIGIN_X + COLS * CELL // 2,
            "y": GAME_ORIGIN_Y + HEADER // 2,
        },
    }
```

- [ ] **Step 3: 从 `game.py` 删掉常量与 `board_config`，改为 import**

`apps/minesweeper/game.py`：删掉原第 12-21 行的常量定义与文件末尾的 `board_config()`，在 import 段加：

```python
from apps.minesweeper.board import (
    CELL,
    COLS,
    GAME_ORIGIN_X,
    GAME_ORIGIN_Y,
    HEADER,
    MINES,
    ROWS,
)
```

模块 docstring 第 1 行改为 `"""tkinter 扫雷游戏：被扫雷视觉 Agent 操作的目标程序。`

- [ ] **Step 4: 更新 `BoardGeometry` 的引用处**

把下列文件中 `from agent_frame.desktop.geometry import BoardGeometry` 改为 `from apps.minesweeper.board import BoardGeometry`：

- `apps/minesweeper/grid.py`
- `apps/minesweeper/build.py`
- `src/agent_frame/tools/desktop/click_cell.py`
- `src/agent_frame/tools/desktop/flag_cell.py`
- `tests/test_desktop_tools.py`
- `tests/test_minesweeper_grid.py`
- `tests/test_minesweeper_game.py`（`test_annotated_frame_contains_row_col_labels` 内）

- [ ] **Step 5: 把两个 `board_config` 测试搬到 `tests/test_minesweeper_board.py`**

从 `tests/test_minesweeper_game.py` 中删掉 `test_board_config_geometry` 与 `test_board_config_region_includes_label_margin`（原第 64-84 行）。

把 `tests/test_minesweeper_board.py` 顶部 import 段整体替换为：

```python
import pytest

from apps.minesweeper.board import (
    CELL,
    COLS,
    GAME_ORIGIN_X,
    GAME_ORIGIN_Y,
    HEADER,
    LABEL_MARGIN_X,
    LABEL_MARGIN_Y,
    ROWS,
    BoardGeometry,
    board_config,
)
```

并在文件末尾追加：

```python
def test_board_config_geometry():
    cfg = board_config()
    assert cfg["geometry"]["origin_x"] == GAME_ORIGIN_X
    assert cfg["geometry"]["origin_y"] == GAME_ORIGIN_Y + HEADER
    assert cfg["geometry"]["cell_w"] == CELL
    assert cfg["geometry"]["cell_h"] == CELL
    assert cfg["geometry"]["rows"] == ROWS
    assert cfg["geometry"]["cols"] == COLS


def test_board_config_region_includes_label_margin():
    cfg = board_config()
    ox, oy = GAME_ORIGIN_X, GAME_ORIGIN_Y + HEADER
    # 区域要向左/上各留出边距，行列标尺才画得进图内
    assert cfg["region"]["left"] == ox - LABEL_MARGIN_X
    assert cfg["region"]["top"] == oy - LABEL_MARGIN_Y
    assert cfg["region"]["width"] == COLS * CELL + LABEL_MARGIN_X
    assert cfg["region"]["height"] == ROWS * CELL + LABEL_MARGIN_Y
    assert cfg["restart"]["type"] == "click"
    assert cfg["restart"]["x"] == GAME_ORIGIN_X + COLS * CELL // 2
    assert cfg["restart"]["y"] == GAME_ORIGIN_Y + HEADER // 2
```

- [ ] **Step 6: 收敛 `tests/test_minesweeper_game.py` 的 import 段**

搬走那两个测试后，本文件只用到 `MinesweeperBoard`（逻辑测试）与 `board_config`（标注可见性测试）。顶部改为：

```python
import base64
import io

from PIL import Image

from apps.minesweeper.board import board_config
from apps.minesweeper.game import MinesweeperBoard
```

- [ ] **Step 7: 跑测试**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: 棋盘几何与常量迁入 apps/minesweeper/board.py

BoardGeometry 是扫雷棋盘的行列换算，不属于通用能力。

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

### Task 10: 三个扫雷工具合并进 `apps/minesweeper/tools.py`，删除 `desktop/`

**Files:**
- Create: `apps/minesweeper/tools.py`
- Delete: `src/agent_frame/tools/desktop/`（3 个文件 + `__init__.py`）、`src/agent_frame/desktop/`（只剩 `__init__.py`）
- Modify: `apps/minesweeper/build.py`
- Move test: `tests/test_desktop_tools.py` → `tests/test_minesweeper_tools.py`

**Interfaces:**
- Consumes: `apps.minesweeper.board.BoardGeometry`、`agent_frame.computer.input.InputController`、`agent_frame.errors.ToolError`
- Produces: `apps.minesweeper.tools.{ClickCellTool, FlagCellTool, RestartGameTool}`；均 `async run(...) -> str` 返回 `"ok"`

- [ ] **Step 1: 迁移测试文件**

```bash
git mv tests/test_desktop_tools.py tests/test_minesweeper_tools.py
```

然后把文件顶部 import 段（原为 `pytest` + `agent_frame.desktop.geometry` + `agent_frame.desktop.mouse` + `agent_frame.tools.desktop` 四行）整体替换为：

```python
import pytest

from agent_frame.computer.input import InputController
from apps.minesweeper.board import BoardGeometry
from apps.minesweeper.tools import ClickCellTool, FlagCellTool, RestartGameTool
```

（`FakeBackend` 与各测试函数体不变；文件内已是 `InputController`。）

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_minesweeper_tools.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.minesweeper.tools'`

- [ ] **Step 3: 新建 `apps/minesweeper/tools.py`**

把三个工具合并进一个文件（内容照搬，只改 import 与参数标注）：

```python
"""扫雷 Agent 可用的工具：翻开、插旗、重开。"""

from __future__ import annotations

from typing import Any, ClassVar

from agent_frame.computer.input import InputController
from agent_frame.errors import ToolError
from apps.minesweeper.board import BoardGeometry


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

    def __init__(self, geometry: BoardGeometry, mouse: InputController) -> None:
        self._geometry = geometry
        self._mouse = mouse

    async def run(self, row: int, col: int) -> str:
        x, y = self._geometry.cell_center(row, col)
        self._mouse.click(x, y, button="left")
        return "ok"


class FlagCellTool:
    name: ClassVar[str] = "flag_cell"
    description: ClassVar[str] = (
        "给指定的格子插旗（标记为此处是雷）。"
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

    def __init__(self, geometry: BoardGeometry, mouse: InputController) -> None:
        self._geometry = geometry
        self._mouse = mouse

    async def run(self, row: int, col: int) -> str:
        x, y = self._geometry.cell_center(row, col)
        self._mouse.shift_click(x, y)
        return "ok"


class RestartGameTool:
    name: ClassVar[str] = "restart_game"
    description: ClassVar[str] = (
        "当本局已经结束（胜利，或踩到雷）时调用，重开一局新游戏。"
        "棋盘未结束时不要调用。"
    )
    parameters: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}

    def __init__(
        self,
        mouse: InputController,
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
            return "ok"
        self._mouse.press(self._key)  # type: ignore[arg-type]
        return "ok"
```

- [ ] **Step 4: 删除框架内的应用工具与 `desktop/` 目录**

```bash
git rm -r src/agent_frame/tools/desktop
git rm -r src/agent_frame/desktop
```

把 `apps/minesweeper/build.py` 的 import 段整体替换为（此后它只依赖框架能力与同应用内的模块）：

```python
from agent_frame.agent import ToolUseAgent
from agent_frame.agent.inputs import StaticText
from agent_frame.computer.input import InputController
from agent_frame.computer.screen import CaptureRegion, ScreenCapture
from agent_frame.computer.sources import ScreenImageSource
from agent_frame.tools import ToolRegistry
from apps.minesweeper.board import BoardGeometry
from apps.minesweeper.grid import GridAnnotator
from apps.minesweeper.prompts import CAPTION, SYSTEM_PROMPT
from apps.minesweeper.tools import ClickCellTool, FlagCellTool, RestartGameTool
```

（`build_registry` 与 `build_agent` 的函数体不变。）

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 6: 验证框架包已无扫雷痕迹**

Run:

```bash
grep -rn "minesweeper\|扫雷\|BoardGeometry\|GridAnnotator" src/agent_frame/ || echo "OK: 框架包已无扫雷痕迹"
grep -rn "import apps\|from apps" src/agent_frame/ || echo "OK: 框架包不依赖 apps"
grep -rn "agent_frame\.desktop" --include=*.py . | grep -v __pycache__ || echo "OK: 无 desktop 残留引用"
```

Expected: 三行都输出 `OK:`

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: 扫雷工具迁入 apps/minesweeper/tools.py，删除框架内 desktop/

框架包 src/agent_frame/ 至此不再出现任何扫雷概念，也不依赖 apps。

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

---

## Phase D：收尾

### Task 11: LLM 图片落盘逻辑归位

**Files:**
- Move: `src/agent_frame/obs/llm_images.py` → `src/agent_frame/llm/image_store.py`
- Move test: `tests/test_llm_images.py` → `tests/test_llm_image_store.py`
- Modify: `src/agent_frame/llm/openai_compat.py:21`

**Interfaces:**
- Consumes: 无
- Produces: `agent_frame.llm.image_store.save_images_and_strip(messages: list[dict], pic_dir: Path) -> list[dict]`（签名与行为不变）

理由：`llm/openai_compat.py` 依赖 `obs`（旁路可观测层）是反向依赖，且该文件只服务 LLM 请求日志。

- [ ] **Step 1: 移动**

```bash
git mv src/agent_frame/obs/llm_images.py src/agent_frame/llm/image_store.py
git mv tests/test_llm_images.py tests/test_llm_image_store.py
```

- [ ] **Step 2: 更新引用**

`src/agent_frame/llm/openai_compat.py` 第 21 行：

```python
from agent_frame.llm.image_store import save_images_and_strip
```

`tests/test_llm_image_store.py` 第 5 行：

```python
from agent_frame.llm.image_store import save_images_and_strip
```

- [ ] **Step 3: 跑测试**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: LLM 请求图片落盘从 obs/ 归位到 llm/image_store.py

obs 是旁路可观测层，不该被 LLM 适配器反向依赖。

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

### Task 12: 文档同步与端到端验证

**Files:**
- Modify: `README.md`
- Rewrite: `docs/minesweeper-agent-flow.md`
- Modify: `docs/roadmap.md`（若其中提到 `desktop` 或 `games/`）

**Interfaces:**
- Consumes: 前 11 个任务的最终结构
- Produces: 与代码一致的文档

- [ ] **Step 1: 更新 README 的模块地图表**

把「模块地图」表里的 `desktop` 行（`| desktop | 桌面自动化：截屏/鼠标控制/棋盘几何/网格标注 + 扫雷工具集 | ✅ 实现 |`）替换为：

```markdown
| `computer` | 通用计算机使用能力：截屏、鼠标/键盘输入、屏幕图源（零领域知识） | ✅ 实现 |
```

并在表格下方补一段：

```markdown
> **仓库分层**：`src/agent_frame/` 是框架与通用能力（与领域无关，不知道「扫雷」的存在）；
> `apps/minesweeper/` 是扫雷应用（游戏本体、棋盘几何、网格标注、提示词、工具、组装）；
> `examples/` 是命令行入口。依赖方向单向：应用可以 import 框架，框架绝不 import 应用。
```

- [ ] **Step 2: 更新 README 其余引用**

- 「快速开始」里扫雷那段的路径 `games/minesweeper.py` 改为 `apps/minesweeper/game.py`。
- 「扫雷视觉 Agent 说明」里「`examples/04_minesweeper_autoplay.py` 自动启动它并对局」的描述改为：自动启动 `apps/minesweeper/game.py` 并对局。
- 全文其余出现 `agent_frame.desktop`、`desktop`、`games/` 的地方，改为 `agent_frame.computer`、`computer`、`apps/minesweeper/`。

- [ ] **Step 3: 重写 `docs/minesweeper-agent-flow.md`**

按新结构重画所有图中的节点名与新路径：

| 旧 | 新 |
|---|---|
| `games/minesweeper.py` | `apps/minesweeper/game.py` |
| `agent_frame.desktop.minesweeper.build_agent` | `apps.minesweeper.build.build_agent` |
| `BoardObserver` | `computer.ScreenImageSource`（+ `apps.minesweeper.grid.GridAnnotator`） |
| `agent_frame.desktop.screen` | `agent_frame.computer.screen` |
| `agent_frame.desktop.mouse` | `agent_frame.computer.input` |
| `agent_frame.desktop.geometry` | `apps.minesweeper.board` |
| `agent_frame.desktop.annotate` | `apps.minesweeper.grid` |
| `agent_frame.tools.desktop/*` | `apps.minesweeper.tools` |
| `agent_frame.obs.llm_images` | `agent_frame.llm.image_store` |
| 「Observer 每轮 `observe()`」 | 「每轮 `build_turn_messages(inputs)` 重新产出本轮输入」 |

「观察帧不进历史」一节改述为：`ToolUseAgent` 每轮请求前调用 `build_turn_messages` 产出**本轮输入**（`TextSource` → 文本消息；`ImageSource` → 带 caption 的图片消息），临时附加在请求末尾，永不进入永久历史。

新增一小节「本轮输入源」，说明 `TextSource` / `ImageSource` 两个协议与 `caption` 的结构性绑定（可直接引用 spec §4.1–4.3）。

- [ ] **Step 4: 全量测试**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 5: 静态检查脚本确认无越界依赖**

```bash
echo "--- 框架包内的扫雷痕迹（应为空）---"
grep -rn "minesweeper\|扫雷\|BoardGeometry\|GridAnnotator" src/agent_frame/ || echo "OK"
echo "--- agent_frame 是否 import apps（应为空）---"
grep -rn "import apps\|from apps" src/agent_frame/ || echo "OK"
echo "--- 残留的 desktop 引用（应为空）---"
grep -rn "agent_frame\.desktop\|tools\.desktop" --include=*.py . | grep -v __pycache__ || echo "OK"
echo "--- 残留的 games 引用（应为空）---"
grep -rn "games\.minesweeper\|from games" --include=*.py . | grep -v __pycache__ || echo "OK"
echo "--- 导入无副作用 ---"
python -c "import agent_frame, apps.minesweeper.build; print('import ok')"
```

Expected: 四段都输出 `OK`，最后输出 `import ok`（不弹窗、不截屏）。

- [ ] **Step 6: 端到端真跑一局（需 API key 与 macOS 辅助功能授权）**

Run: `MODEL=deepseek-flash python examples/04_minesweeper_autoplay.py`

Expected:
- 扫雷窗口打开并置顶，Agent 持续翻格 / 插旗推进棋盘；
- `log/llm.log` 有请求与回包记录；
- `log/pic/*.png` 有截图落盘；
- Ctrl+C 可中断。

若鼠标不动作，检查 macOS「系统设置 → 隐私与安全性 → 辅助功能」是否已授权终端/Python。

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "$(cat <<'EOF'
docs: 同步 README 与扫雷调用流程图到三层结构

Co-Authored-By: Claude Code <noreply@anthropic.com>
EOF
)"
```

---

## 完成标准

- [ ] `pytest` 全绿。
- [ ] `grep -rn "minesweeper\|扫雷\|BoardGeometry\|GridAnnotator" src/agent_frame/` 无输出。
- [ ] `grep -rn "from apps" src/agent_frame/` 无输出。
- [ ] `src/agent_frame/desktop/`、`games/`、`src/agent_frame/tools/desktop/` 三个目录已不存在。
- [ ] `agent_frame/agent/inputs.py` 与 `agent_frame/computer/sources.py` 存在且被 `apps.minesweeper.build` 使用。
- [ ] `MODEL=deepseek-flash python examples/04_minesweeper_autoplay.py` 能真跑一局。
