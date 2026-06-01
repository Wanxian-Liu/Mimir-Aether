# ENG-CLI-01: CLI `--one-shot` 模式

## 做了什么

为 MimirAether CLI 添加 `--one-shot` 模式（PI-L06 #3），使 CLI 可非交互单次调用，方便 script/CI 集成。

### 设计

- **新增根级别 flag** `--one-shot PROMPT` — 不是子命令，不打断现有 CLI 结构
- **新增 handler** `cmd_one_shot()` in `mimir_cli/main.py`:
  - 创建 `MimirAetherAgent`（quiet 模式 — 无横幅、无装饰）
  - 调用 `agent.run_conversation(prompt)`
  - 仅打印纯文本结果到 stdout
  - 适合 `mimir --one-shot "summarize this"` 管线化调用
- **parsing 集成** `main()` 在 `--version` 之后、`--resume` 之前检查 `args.one_shot`
- **epilog 更新** `cli_subparsers_setup.py` 示例行 + `--one-shot` 参数注册
- `cli.py` docstring 更新

### 使用方式

```bash
# 基本用法
mimir --one-shot "一个简单的文案"

# 与 skills 组合
mimir --one-shot "list all cron jobs" --skills cronjob

# 管线化 (不用交互)
mimir --one-shot "Explain the current repo structure" | head -20
```

### 风险

极低。`--one-shot` 是新增 flag 且仅在显式调用时触发，不影响默认交互模式。

### 建议 commit message

```
feat(cli): add --one-shot non-interactive mode

- Root-level --one-shot PROMPT flag for script/CI integration
- cmd_one_shot handler: creates agent, runs conversation, prints raw response
- tests/tools/test_cli_one_shot.py: 5 tests
- Usage: mimir --one-shot "what's the weather?"
```
