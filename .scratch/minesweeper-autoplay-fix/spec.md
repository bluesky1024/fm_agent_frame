# 扫雷自动对局提前退出修复

**Status:** done
**Date:** 2026-10-17

## Problem Statement

运行 `python examples/04_minesweeper_autoplay.py` 时，对局没有打完就结束。两轮排查确认了四个根因：

1. `ContextBuilder` 把观察帧插在历史之前，模型把截图理解为开局旧图，而不是点击后的当前状态。
2. runtime 的「无 tool_calls 即结束」语义让「请提供最新截图」这类纯文本响应直接收尾。
3. 同一批工具调用会并行执行：3 个 `flag_cell`（Shift+点击）与 2 个 `click_cell` 交错，普通点击被 Shift 修饰或直接丢失；但坐标去重又把这两格永久锁死，模型无法重试。
4. 模型在只剩 2 个安全格未翻开（已翻开 76/78）时输出「本局结束：胜利（所有非雷格都已翻开）」；结论解析因行尾括号没有命中，示例继续空转，最后被用户取消，因此没有任何结束信息。

## Solution

- `ContextProvider` 支持 `placement = "after_history"`；扫雷观察帧追加在请求末尾，只提供最新一帧。
- 模型协议二选一：调用工具，或单独输出固定结束结论。
- 鼠标操作在 `MouseController` 内串行化，保证 `shift_click` 的 keyDown→click→keyUp 原子执行。
- 新增 `board_state.py`：从截图读取已翻开/未翻开/插旗/踩雷，胜负由应用层校验，模型结论不直接决定退出（ADR-0009）。
- 观察 caption 动态给出雷数、已翻开、未翻开、插旗数与胜利目标；系统提示词写明雷数与胜利条件。
- `run_autoplay` 在每次运行后读图判定：已结束则退出；未结束则追加带棋盘计数的提示继续，最多 3 次。
- `ClickCellTool` 点击前用最近一帧核对格子状态（已翻开/已插旗返回可恢复错误），允许丢失点击后重试。
- 示例捕获 `KeyboardInterrupt` 并打印「已取消」。
- 一局制：移除 `restart_game` 工具与 restart 配置。

## Acceptance

- `pytest` 全绿。
- 真实对局中模型持续翻格/插旗，不再索要截图；误报胜利不会导致提前退出。
- 一局真正结束时打印 `本局结束：胜利` 或 `本局结束：失败` 并退出；Ctrl+C 打印「已取消」。
- 请求视图末尾始终只有一张最新截图，历史中不累积图片。
