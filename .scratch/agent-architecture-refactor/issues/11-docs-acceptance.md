# 11: 文档、示例 04 与全量验收

**What to build:** 文档、示例与最终目录完全一致，全量本地检查通过，框架达到"基本完备版本"，并准备好真实 API 的人工验收清单。

**Blocked by:** 06, 07, 08, 09, 10

**Status:** done

- [x] README、学习路线与架构文档与最终目录一致
- [x] 扫雷示例使用新运行时与应用目录
- [x] 本地检查命令的 lint、format、类型、依赖与测试全部通过
- [x] 基本完备版本定义全部满足：示例可跑、每项能力有最小实现或空实现且真实接线、事件流与 trace 可见、旧路径删除
- [x] 真实 API 人工验收清单准备就绪（本票不执行真实 API）
- [x] 无失效文档引用与旧路径残留

## Comments

- 2026-10-17: 完成。重写 README 与 roadmap，更新 architecture/minesweeper flow，新增 `docs/acceptance.md`（真实 API 人工验收清单，未执行）；重构计划标记完成并保留人工验收未勾选。补充最小 `interfaces/cli.py`（文档中已列出的能力）。`python scripts/check.py` 全绿：ruff、format、mypy（核心四包严格）、import-linter 5 条契约、142 passed（含 fake-LLM 扫雷 e2e）。示例 01–04 均可导入；示例 02 生成 `log/trace.jsonl`。旧模块路径与失效文档引用扫描为空。
