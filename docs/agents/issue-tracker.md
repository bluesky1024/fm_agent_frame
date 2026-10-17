# Issue tracker：本地 Markdown

本仓库的 issue 与 spec 以 markdown 文件形式存放在 `.scratch/` 下。

## 约定

- 每个功能一个目录：`.scratch/<feature-slug>/`
- spec 为 `.scratch/<feature-slug>/spec.md`
- 实现 issue 每个 ticket 一个文件：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`，从 `01` 开始编号，绝不使用单个合并的 tickets 文件
- triage 状态记录在每个 issue 文件顶部的 `Status:` 行（角色字符串见 `triage-labels.md`）
- 实现完成后把 `Status:` 设为 `done`（实现完成状态，不属于 triage 词表）
- 评论与对话历史追加到文件底部的 `## Comments` 标题下

## 当 skill 要求 "publish to the issue tracker" 时

在 `.scratch/<feature-slug>/` 下新建文件（必要时创建目录）。

## 当 skill 要求 "fetch the relevant ticket" 时

读取引用路径处的文件。用户通常会直接提供路径或 issue 编号。

## Wayfinding 操作

由 `/wayfinder` 使用。**map** 是一个文件，每个 ticket 对应一个 **child** 文件。

- **Map**：`.scratch/<effort>/map.md`（包含 Notes / Decisions-so-far / Fog 正文）。
- **Child ticket**：`.scratch/<effort>/issues/NN-<slug>.md`，从 `01` 开始编号，正文为问题。`Type:` 行记录 ticket 类型（`research`/`prototype`/`grilling`/`task`）；`Status:` 行记录 `claimed`/`resolved`。
- **Blocking**：文件顶部的 `Blocked by: NN, NN` 行。当它列出的每个文件都是 `resolved` 时，该 ticket 即解除阻塞。
- **Frontier**：扫描 `.scratch/<effort>/issues/`，找打开、未阻塞、未认领的文件；编号最小者优先。
- **Claim**：开始任何工作前设置 `Status: claimed` 并保存。
- **Resolve**：在 `## Answer` 标题下追加答案，设置 `Status: resolved`，然后把上下文指针（要点 + 链接）追加到 `map.md` 的 Decisions-so-far 中。
