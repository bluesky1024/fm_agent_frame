# 扫雷视觉 Agent 跨平台适配实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让扫雷视觉 Agent 同时适配 Windows 与 macOS，坐标在任意平台/缩放下对齐，目标程序统一为网页扫雷。

**Architecture:** 在 `ScreenCapture` 内做尺度探测与归一化，使 `grab()` 返回的图像永远与 pyautogui 屏幕坐标 1:1；`load_config` 按 `sys.platform` 从 `config/minesweeper.json` 的 `windows`/`macos` section 选对应配置并平铺返回。`build_registry`/`build_agent` 接口不变。

**Tech Stack:** Python 3.12、mss、pyautogui、Pillow、pytest。

**Spec:** [docs/superpowers/specs/2026-10-12-minesweeper-cross-platform-design.md](../specs/2026-10-12-minesweeper-cross-platform-design.md)

## Global Constraints

- 坐标约定 1 基行列号，`BoardGeometry.origin_x/origin_y` 是屏幕坐标中棋盘左上角格子外沿。
- `MouseController`/`ScreenCapture` 的底层 GUI 库（pyautogui/mss）**延迟导入**，测试注入 fake，不碰真屏幕。
- `scale == 1.0` 时 `grab()` 必须**原样转发** `self._grab(self._region)`（零开销、region 引用不变），保证现有 `test_grab_delegates_to_grabber_with_region` 不破坏。
- `build_registry(config, mouse)` / `build_agent(config, llm, *, mouse, capture)` 签名不变，接收平铺 config。
- 全量 `python -m pytest -v` 全绿，不依赖真实屏幕/API。

## Review Focus

以下输入类/失败模式是 spec 隐含、但需专门测试钉住的最可能咬人的点：

1. **config 缺当前平台 section**：用户校准 config 时漏写 `windows` 或 `macos` section，`load_config` 应报明确的 `ValueError` 而非裸 `KeyError`。→ Task 2 测试。
2. **未知平台**：在非 `win32`/`darwin` 平台运行，应报 `ValueError` 而非静默或 `KeyError`。→ Task 2 测试。
3. **scale≠1 时图像尺寸**：归一化后 `grab()` 返回的图像尺寸必须 == region 逻辑尺寸，否则标注坐标全错。→ Task 1 测试。
4. **scale≠1 时 grab 区域换算**：grabber 收到的是 ×scale 的 mss 坐标 region，否则截的是错误区域。→ Task 1 测试。
5. **scale=1 零开销**：注入 grabber 且未传 scale 时，不应探测真实屏幕（避免测试/CI 环境 import mss/pyautogui），region 引用不变。→ Task 1 现有测试回归。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `src/agent_frame/desktop/screen.py` | 改 | `ScreenCapture` 加 scale 归一化 + `_detect_scale` + `mss.MSS` |
| `src/agent_frame/desktop/minesweeper.py` | 改 | `load_config` 按平台选 section 并平铺 |
| `config/minesweeper.json` | 改 | 分 `windows`/`macos` section + 共享字段 |
| `tests/test_desktop_screen.py` | 改 | 新增 scale 归一化测试 |
| `tests/test_minesweeper_build.py` | 改 | 新增 `load_config` 平台选择测试 |
| `README.md` | 改 | 跨平台用法 + 校准说明 |

---

### Task 1: ScreenCapture 缩放归一化

**Files:**
- Modify: `src/agent_frame/desktop/screen.py`
- Test: `tests/test_desktop_screen.py`

**Interfaces:**
- Produces: `ScreenCapture(region, grabber=None, *, scale: float | None = None)`；`ScreenCapture.grab() -> Image.Image`（归一化到逻辑坐标）；`_detect_scale() -> float`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_desktop_screen.py` 末尾追加：

```python
def test_grab_resizes_when_scale_is_not_one():
    region = CaptureRegion(left=0, top=0, width=30, height=40)
    seen = {}

    def fake_grabber(r):
        seen["region"] = r
        # 模拟 mss 返回物理像素（2x）
        return Image.new("RGB", (r.width, r.height), "white")

    cap = ScreenCapture(region, grabber=fake_grabber, scale=2.0)
    img = cap.grab()

    # 图像归一化到逻辑尺寸
    assert img.size == (30, 40)
    # grabber 收到的是 ×2 的 mss 坐标
    assert seen["region"].width == 60
    assert seen["region"].height == 80
    assert seen["region"].left == 0
    assert seen["region"].top == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_desktop_screen.py -v`
Expected: FAIL —— `TypeError: ScreenCapture.__init__() got an unexpected keyword argument 'scale'`

- [ ] **Step 3: 实现 screen.py**

把 `src/agent_frame/desktop/screen.py` 全文替换为：

```python
"""截屏：把屏幕上一块矩形区域抓成 PIL 图像。

返回的图像始终与 pyautogui 屏幕坐标 1:1 对应：当底层截屏库返回
物理像素（如 macOS Retina 2x 或 Windows 未 DPI-aware）时，grab()
会按 scale 把图像归一化回逻辑尺寸。
"""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image
from pydantic import BaseModel


class CaptureRegion(BaseModel):
    """截屏区域（屏幕坐标）。"""

    left: int
    top: int
    width: int
    height: int


Grabber = Callable[[CaptureRegion], Image.Image]


class ScreenCapture:
    """按区域截屏。默认用 mss；测试可注入 grabber。

    scale 是「mss 物理像素 / pyautogui 逻辑点」的比值：
    - 生产（无 grabber、无 scale）：首次 grab() 惰性探测并缓存。
    - 注入 grabber 且未显式传 scale：视为 1.0（grabber 返回的即屏幕坐标图）。
    - 显式传 scale：可测试归一化行为。
    """

    def __init__(
        self,
        region: CaptureRegion,
        grabber: Grabber | None = None,
        *,
        scale: float | None = None,
    ) -> None:
        self._region = region
        self._grab = grabber or _default_grabber
        if scale is not None:
            self._scale = scale
        elif grabber is not None:
            self._scale = 1.0
        else:
            self._scale = None  # 生产路径：首次 grab 时探测

    @property
    def region(self) -> CaptureRegion:
        return self._region

    def grab(self) -> Image.Image:
        scale = self._scale
        if scale is None:
            scale = _detect_scale()
            self._scale = scale
        if scale == 1.0:
            return self._grab(self._region)
        mss_region = CaptureRegion(
            left=int(self._region.left * scale),
            top=int(self._region.top * scale),
            width=int(self._region.width * scale),
            height=int(self._region.height * scale),
        )
        img = self._grab(mss_region)
        return img.resize((self._region.width, self._region.height))


def _detect_scale() -> float:
    """探测 mss 物理像素与 pyautogui 逻辑点的比值（取主屏）。"""
    import mss
    import pyautogui

    with mss.MSS() as sct:
        mss_w = sct.monitors[1]["width"]
    logical_w = pyautogui.size().width
    return round(mss_w / logical_w, 3) if logical_w else 1.0


def _default_grabber(region: CaptureRegion) -> Image.Image:
    import mss  # 延迟导入，避免测试环境需要截屏依赖

    with mss.MSS() as sct:
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

- [ ] **Step 4: 运行测试确认通过 + 回归**

Run: `python -m pytest tests/test_desktop_screen.py -v`
Expected: 全部 PASS（含既有 `test_grab_delegates_to_grabber_with_region` 与新增 `test_grab_resizes_when_scale_is_not_one`）

- [ ] **Step 5: 提交**

```bash
git add src/agent_frame/desktop/screen.py tests/test_desktop_screen.py
git commit -m "feat: normalize screen capture to pyautogui coordinates via scale"
```

---

### Task 2: 配置分平台（load_config + config 结构）

**Files:**
- Modify: `src/agent_frame/desktop/minesweeper.py`
- Modify: `config/minesweeper.json`
- Test: `tests/test_minesweeper_build.py`

**Interfaces:**
- Consumes: 无（沿用 `load_config(path) -> dict` 签名）。
- Produces: `load_config(path: str | Path) -> dict`，返回平铺单平台 config（`geometry`/`region`/`restart`/`image_detail`/`image_max_px`/`max_steps`）；`_platform_key(platform: str) -> str`。

- [ ] **Step 1: 写失败测试**

把 `tests/test_minesweeper_build.py` 顶部导入区改为：

```python
import json
import sys

import pytest
from PIL import Image

from agent_frame.desktop.minesweeper import build_agent, build_registry, load_config
from agent_frame.desktop.mouse import MouseController
from agent_frame.desktop.screen import CaptureRegion, ScreenCapture
```

然后在文件末尾追加：

```python
def test_load_config_selects_platform_section(monkeypatch, tmp_path):
    data = {
        "windows": {
            "geometry": {"origin_x": 1, "origin_y": 2, "cell_w": 10, "cell_h": 10, "rows": 9, "cols": 9},
            "region": {"left": 0, "top": 0, "width": 100, "height": 100},
            "restart": {"type": "click", "x": 50, "y": 50},
        },
        "macos": {
            "geometry": {"origin_x": 11, "origin_y": 22, "cell_w": 12, "cell_h": 12, "rows": 9, "cols": 9},
            "region": {"left": 0, "top": 0, "width": 120, "height": 120},
            "restart": {"type": "click", "x": 60, "y": 60},
        },
        "image_detail": "high",
        "image_max_px": 1300,
        "max_steps": 300,
    }
    path = tmp_path / "minesweeper.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(sys, "platform", "darwin")
    cfg = load_config(path)
    assert cfg["geometry"] == data["macos"]["geometry"]
    assert cfg["region"] == data["macos"]["region"]
    assert cfg["image_detail"] == "high"
    assert cfg["image_max_px"] == 1300
    assert cfg["max_steps"] == 300

    monkeypatch.setattr(sys, "platform", "win32")
    cfg = load_config(path)
    assert cfg["geometry"] == data["windows"]["geometry"]


def test_load_config_unknown_platform_raises(monkeypatch, tmp_path):
    data = {
        "windows": {
            "geometry": {"origin_x": 0, "origin_y": 0, "cell_w": 10, "cell_h": 10, "rows": 9, "cols": 9},
            "region": {"left": 0, "top": 0, "width": 100, "height": 100},
            "restart": {"type": "click", "x": 50, "y": 50},
        },
        "image_max_px": 1300,
    }
    path = tmp_path / "minesweeper.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(ValueError):
        load_config(path)


def test_load_config_missing_platform_section_raises(monkeypatch, tmp_path):
    data = {"image_max_px": 1300}  # 缺 windows/macos section
    path = tmp_path / "minesweeper.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(ValueError):
        load_config(path)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_minesweeper_build.py -v`
Expected: FAIL —— `test_load_config_selects_platform_section` 断言失败（当前 `load_config` 直接返回原始 json，`cfg["geometry"]` 触发 `KeyError`）

- [ ] **Step 3: 实现 load_config**

把 `src/agent_frame/desktop/minesweeper.py` 顶部导入区加 `import sys`，并把 `load_config` 函数替换为：

```python
def load_config(path: str | Path) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    key = _platform_key(sys.platform)
    if key not in raw:
        raise ValueError(f"config 缺少平台 section: {key}")
    section = raw[key]
    merged = {
        "geometry": section["geometry"],
        "region": section["region"],
        "restart": section["restart"],
    }
    for k in ("image_detail", "image_max_px", "max_steps"):
        if k in raw:
            merged[k] = raw[k]
    return merged


def _platform_key(platform: str) -> str:
    if platform == "win32":
        return "windows"
    if platform == "darwin":
        return "macos"
    raise ValueError(f"不支持的平台: {platform}，仅支持 windows/macos")
```

（`import sys` 加在 `import json` 之后、`from pathlib import Path` 附近即可。）

- [ ] **Step 4: 改 config/minesweeper.json 为分平台结构**

把 `config/minesweeper.json` 全文替换为：

```json
{
  "_comment": "校准说明：origin_x/origin_y 是棋盘左上角格子外沿的屏幕坐标；cell_w/cell_h 是单格宽高；region 是截屏区域。windows/macos 两个 section 各自校准（网页扫雷窗口位置/大小不同）。restart 支持 type=click(x,y) 或 type=key(key)。",
  "windows": {
    "geometry": { "origin_x": 380, "origin_y": 260, "cell_w": 24, "cell_h": 24, "rows": 9, "cols": 9 },
    "region": { "left": 340, "top": 220, "width": 280, "height": 280 },
    "restart": { "type": "click", "x": 470, "y": 230 }
  },
  "macos": {
    "geometry": { "origin_x": 380, "origin_y": 260, "cell_w": 24, "cell_h": 24, "rows": 9, "cols": 9 },
    "region": { "left": 340, "top": 220, "width": 280, "height": 280 },
    "restart": { "type": "click", "x": 470, "y": 230 }
  },
  "image_detail": "high",
  "image_max_px": 1300,
  "max_steps": 300
}
```

- [ ] **Step 5: 运行测试确认通过 + 回归**

Run: `python -m pytest tests/test_minesweeper_build.py -v`
Expected: 全部 PASS（含既有三个 build 测试与新增三个 load_config 测试）

- [ ] **Step 6: 提交**

```bash
git add src/agent_frame/desktop/minesweeper.py config/minesweeper.json tests/test_minesweeper_build.py
git commit -m "feat: select per-platform config section in load_config"
```

---

### Task 3: README 跨平台文档

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新快速开始第 5 步为跨平台说明**

把 `README.md` 中：

```bash
# 5. 扫雷视觉 Agent（多模态计算机使用，需先校准 config/minesweeper.json）
#    Windows；安装桌面依赖：pip install -e ".[desktop]"
MODEL=deepseek-flash python examples/04_minesweeper_agent.py
```

替换为：

```bash
# 5. 扫雷视觉 Agent（多模态计算机使用，需先校准 config/minesweeper.json）
#    Windows / macOS；安装桌面依赖：pip install -e ".[desktop]"
MODEL=deepseek-flash python examples/04_minesweeper_agent.py
```

- [ ] **Step 2: 在「快速开始」代码块后追加校准说明**

在快速开始代码块的 ` ``` ` 结束后（即 `## 运行测试` 之前）追加：

```markdown
### 扫雷视觉 Agent 校准（Windows / macOS）

目标程序统一为网页版扫雷（两个平台开同一网页）。首次运行前：

1. 打开网页版扫雷，固定浏览器窗口位置与大小。
2. 截一张棋盘截图，量出：棋盘左上角格子的屏幕坐标、单格宽高、截屏区域。
3. 把数值填入 `config/minesweeper.json` 的 `windows` 或 `macos` 对应 section。
4. macOS 需在「系统设置 → 隐私与安全性 → 辅助功能」授权终端/Python 控制鼠标。
```

- [ ] **Step 3: 提交**

```bash
git add README.md
git commit -m "docs: document cross-platform minesweeper calibration"
```

---

## 人工验收（实现完成后，需真机运行）

1. `python -m pytest -v` 全绿，且不依赖真实屏幕/API。
2. Windows 与 macOS 各用网页扫雷、按上面校准说明填好 `config/minesweeper.json` 后，`MODEL=deepseek-flash python examples/04_minesweeper_agent.py` 能截屏 → 标注 → 模型看图 → 点击棋盘 → 再截屏，形成闭环。
3. 在 scale != 1 的环境（Windows 未 DPI-aware 或 mss 返回物理像素的 Retina 屏），截图仍与点击坐标一致（`ScreenCapture` 归一化生效）。
