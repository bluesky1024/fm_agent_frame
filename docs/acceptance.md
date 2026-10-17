# 真实 API 人工验收清单

自动测试全部使用 fake LLM，不访问真实网络。以下步骤在重构达到「基本完备版本」后人工执行。

## 前置条件

- `py312` 环境中已安装：`pip install -e ".[dev,desktop,server]"`
- `.env` 中已配置 `DEEPSEEK_API_KEY`
- 清空或备份 `log/` 目录，便于检查本轮生成物

## 1. 工具调用与流式输出

```bash
python examples/02_tool_agent.py
# 输入：3 的 4 次方加 10 是多少？
```

- [ ] 终端能看到 `LLMDelta` 的流式文本
- [ ] 事件流包含 `ToolCallRequested` 与 `ToolResult`
- [ ] 最终答案正确（91）
- [ ] `log/trace.jsonl` 每行是合法 JSON，包含 `run_start` / `run_end`

## 2. 多轮对话与历史

```bash
python examples/03_interactive.py
# 第一轮：我叫小明
# 第二轮：我叫什么？
```

- [ ] 第二轮能正确回答「小明」
- [ ] `log/llm.log` 中每轮请求只有一条 system 消息（无重复累积）
- [ ] 工具轮中 assistant 的文本没有被丢弃

## 3. 工具错误回填

向示例 02 提问，诱导模型传入非法参数（如让 calculator 计算不支持的表达式）：

- [ ] 工具参数不符合 schema 时返回结构化错误，且工具未执行
- [ ] 错误被回填为 tool 消息，流程不中断，模型能自行纠正

## 4. 步数超限与取消

- [ ] 将 `max_steps` 调小并给一个需要多步的任务，事件流以 `Error` + `RunEnd` 收尾
- [ ] Ctrl+C 取消长任务时，进程能正常退出，不留下挂起的鼠标按键

## 5. 扫雷自动对局

```bash
MODEL=deepseek-flash python examples/04_minesweeper_autoplay.py
```

- [ ] 游戏窗口自动启动，Agent 能持续观察并操作
- [ ] 翻格、插旗工具均生效；点击已翻开/已插旗的格子会收到可恢复错误并继续
- [ ] 同一批 flag/click 串行执行，不因 Shift 交错而丢失点击
- [ ] 观察帧不累积进历史，且始终是请求里的最后一条消息（`log/llm.log` 每轮只有一帧最新截图）
- [ ] 观察说明包含雷数、已翻开、未翻开与插旗计数
- [ ] 模型误报胜利时不会提前退出；应用层读图校验后追加提示继续（最多 3 次）
- [ ] 一局真正结束（胜利或踩雷）后打印 `本局结束：胜利` 或 `本局结束：失败` 并自动退出
- [ ] Ctrl+C 取消时打印「已取消」

## 6. 日志生成

- [ ] `log/agent.log`、`log/llm.log`、`log/trace.jsonl` 均生成
- [ ] `log/pic/*.png` 中有去重后的截图
- [ ] 日志内容可读，无 base64 图片直写
