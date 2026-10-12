# 扫雷视觉 Agent 跨平台适配设计

- 日期：2026-10-12
- 状态：已确认（待实现）
- 类型：框架能力扩展（跨平台计算机使用）
- 前置：[扫雷视觉 Agent 设计](2026-10-11-minesweeper-vision-agent-design.md)

## 1. 目标与定位

现有扫雷视觉 Agent 最初只按 Windows 设计（`enable_dpi_awareness` 处理 Windows DPI 缩放，目标程序是 Microsoft Minesweeper）。本次改造让它**同时适配 Windows 和 macOS**，目标程序统一为网页版扫雷，坐标在任意平台/缩放下都能对齐。

关键决策：

| 决策项 | 结论 |
|---|---|
| 坐标缩放健壮性 | 健壮缩放抽象——运行时探测 scale factor，防御性地保证「mss 截图像素 ↔ pyautogui 点击坐标」永远 1:1 对齐，不依赖库的碰巧行为 |
| 抽象位置 | 内置在 `ScreenCapture`（`screen.py`），`BoardObserver`/`BoardGeometry`/`GridAnnotator` 无感知 |
| 目标程序 | 统一网页扫雷（Windows 与 macOS 都开同一网页，浏览器窗口固定） |
| 配置组织 | 单一 `config/minesweeper.json` 含 `windows`/`macos` 两个 section，运行时按平台自动选 |

## 2. 现有架构要点（改动基线）

- `ScreenCapture(region, grabber=None)`：`grab()` 委托 `_default_grabber`（mss）或注入的 `grabber`。`_default_grabber` 用 `mss.mss()` grab 区域，`Image.frombytes` 转 PIL 图。
- `MouseController`：`enable_dpi_awareness()` 在 Windows 上调 `SetProcessDpiAwareness`，非 Windows 为 no-op。
- `minesweeper.py`：`load_config(path)` 直接 `json.loads` 读文件；`build_registry(config, mouse)` / `build_agent(config, llm, *, mouse, capture)` 接收**平铺的** config（含 `geometry`/`region`/`restart`/`image_detail`/`image_max_px`/`max_steps`）。
- `config/minesweeper.json`：平铺的示例配置，坐标是需校准的占位值。
- 坐标约定：行列号 1 基；`BoardGeometry.origin_x/origin_y` 是屏幕坐标中棋盘左上角格子外沿。

## 3. 实测事实（设计依据）

在目标 MacBook Pro（macOS 15，Retina）实测：

| 项 | 值 |
|---|---|
| `NSScreen.backingScaleFactor` | 2.0（物理 3360×2100） |
| `pyautogui.size()` | 1680×1050（逻辑点） |
| `mss` 全屏像素 | 1680×1050（逻辑点，已除以 2） |

即这台机器上 mss 与 pyautogui 恰好都用逻辑点、坐标自洽（scale=1）。但这是 mss 在 macOS 上的隐含行为，不保证在所有环境成立（Windows 未 DPI-aware、或 mss 未来返回物理像素时，两者会差 2 倍）。健壮抽象的意义就是消除这个隐含假设。

## 4. 改动设计

### 4.1 缩放抽象（`screen.py` 内置）

`ScreenCapture` 增加尺度探测与归一化，使 `grab()` 返回的图像永远与 pyautogui 屏幕坐标 1:1 对应。

**接口：**

```python
class ScreenCapture:
    def __init__(self, region: CaptureRegion, grabber: Grabber | None = None,
                 *, scale: float | None = None) -> None:
        ...
```

- `scale=None`（缺省）：生产路径，首次 `grab()` 惰性探测并缓存。
- 注入 `grabber` 且未显式传 `scale`：视为 `1.0`（测试场景，grabber 返回的就是屏幕坐标图），**保持现有测试语义**。
- 显式传 `scale`：可测试归一化行为。

**探测：**

```python
def _detect_scale() -> float:
    import mss
    import pyautogui
    with mss.MSS() as sct:
        mss_w = sct.monitors[1]["width"]   # 主屏像素宽
    logical_w = pyautogui.size().width     # pyautogui 逻辑宽
    return round(mss_w / logical_w, 3) if logical_w else 1.0
```

多显示器只取主屏（`monitors[1]`）；扫雷场景为单屏，够用。

**`grab()` 归一化：**

- `scale == 1.0`：`return self._grab(self._region)`（原样转发，向后兼容）。
- `scale != 1.0`：把 region 换算到 mss 坐标系（`× scale`）grab，再把得到的图 `resize` 到 `(region.width, region.height)` 逻辑尺寸返回。

### 4.2 配置分平台（`minesweeper.py` 的 `load_config`）

> **后续变更（已移除）**：项目最终只保留自研扫雷（`games/minesweeper.py`，几何由 `board_config()` 自报、免校准），
> 已删除 `config/minesweeper.json` 与 `load_config`/`_platform_key`。本节保留为当时的设计记录；
> 跨平台中仍生效的是 §4.1 的坐标缩放归一化。

`config/minesweeper.json` 结构改为：

```json
{
  "_comment": "校准说明…",
  "windows": { "geometry": {...}, "region": {...}, "restart": {...} },
  "macos":   { "geometry": {...}, "region": {...}, "restart": {...} },
  "image_detail": "high",
  "image_max_px": 1300,
  "max_steps": 300
}
```

`load_config(path)` 读文件后按 `sys.platform` 选 section（`win32` → `windows`，`darwin` → `macos`），合并顶层共享字段，返回**平铺的**单平台 config：

```python
{
  "geometry": {...}, "region": {...}, "restart": {...},
  "image_detail": "high", "image_max_px": 1300, "max_steps": 300
}
```

`build_registry(config, mouse)` / `build_agent(config, llm, *, mouse, capture)` **接口不变**，因此现有 `tests/test_minesweeper_build.py` 的平铺 `_config()` 无需改动。

未知平台（`sys.platform` 非 `win32`/`darwin`）报 `ValueError`，提示仅支持 windows/macos。

### 4.3 目标程序

统一网页扫雷（Windows 与 macOS 各开一个浏览器窗口跑同一网页版扫雷）。窗口位置与大小固定后，量一张截图填各自 section 的坐标。目标程序是运行环境层面的选择，不改框架代码；README 提供校准说明。

### 4.4 `mss.mss` → `mss.MSS`

随 `screen.py` 改动一起，把弃用的 `mss.mss()` 换成 `mss.MSS()`（当前 mss 10.x 均可用，未来版本会移除旧名）。

## 5. 影响面

**改动文件：**

| 文件 | 动作 |
|---|---|
| `src/agent_frame/desktop/screen.py` | 改：scale 探测 + grab 归一化 + `mss.MSS` |
| `src/agent_frame/desktop/minesweeper.py` | 改：`load_config` 按平台选 section |
| `config/minesweeper.json` | 改：分平台 section 结构 |
| `tests/test_desktop_screen.py` | 改：新增归一化测试 |
| `tests/test_minesweeper_build.py` | 改：新增 `load_config` 平台选择测试 |
| `README.md` | 改：跨平台用法 + 校准说明 |

**不改动：** `mouse.py`（`enable_dpi_awareness` 保留，与缩放抽象配合）、`geometry.py`、`annotate.py`、`observer.py`、三个工具、`messages.py`、`openai_compat.py`、`agent/*`。

## 6. 测试策略

- `test_desktop_screen.py`：
  - 回归：`scale=1`（注入 grabber）原样转发，`seen["region"] is region` 仍成立。
  - 新增：注入 `grabber` + `scale=2.0`，断言 `grab()` 返回的图像 resize 到逻辑尺寸、且 grabber 收到的是 ×2 的 mss 坐标 region。
- `test_minesweeper_build.py`：
  - 新增：构造含 `windows`/`macos` section 的 config 文件（或 dict），monkeypatch `sys.platform` 为 `win32`/`darwin`，断言 `load_config` 返回平铺的对应 section + 共享字段。
- 全量回归：现有 42 测试 + 新增，全绿，不依赖真实屏幕/API。

## 7. 验收标准

1. `python -m pytest -v` 全绿，不依赖真实屏幕/API。
2. Windows 与 macOS 上，`MODEL=deepseek-flash python examples/04_minesweeper_autoplay.py`（自研扫雷，免校准）能截屏 → 标注 → 模型看图 → 点击棋盘 → 再截屏，形成闭环。
3. 坐标对齐不依赖「mss 恰好返回逻辑点」的隐含假设：`scale != 1` 的环境下（如 Windows 未 DPI-aware 的物理像素截图，或 mss 返回物理像素的 Retina 屏）截图仍与点击坐标一致。
