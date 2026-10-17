# 10: 计算机使用与扫雷应用迁移

**What to build:** 通用截屏、鼠标、观察与标注能力成为框架的一等能力；扫雷的棋盘几何、工具、提示词与启动逻辑迁移为独立应用，并在无真实 API 的情况下完成一局端到端验证。

**Blocked by:** 05

**Status:** done

- [x] 截屏、鼠标、观察与标注迁入通用能力层，同步调用不阻塞事件循环
- [x] 屏幕与鼠标后端以协议暴露，测试可替换为假实现
- [x] 扫雷棋盘几何、点击/插旗/重开工具、提示词与启动逻辑位于独立应用目录
- [x] 旧桌面应用路径删除，循环导入消失
- [x] 假 LLM 加假后端可完成启动、观察、操作、结束的完整 e2e
- [x] 目标扫雷程序未被修改
- [x] 测试全绿，依赖检查通过

## Comments

- 2026-10-17: 实现完成。`capabilities/computer_use` 提供 ScreenBackend/MouseBackend 协议、ScreenCapture、MouseController、GridAnnotator 与 ScreenObserver；截屏/标注/PNG 编码经 `asyncio.to_thread` 隔离，鼠标工具同样走线程。新建 `apps/minesweeper`（board/config/observer/prompt/tools/agent/launcher），删除 `desktop/` 与 `tools/desktop/`；示例 04 改用应用入口。假 LLM + 假屏幕/鼠标后端 e2e 覆盖观察 4 次、翻格/插旗/重开与结束；`games/` 无改动。全量 140 passed。
