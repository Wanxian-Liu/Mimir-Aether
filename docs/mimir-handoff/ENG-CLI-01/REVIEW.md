# ENG-CLI-01: Cursor 复核重点

## 1. 设计合规

- **最小化**：仅加 24 行 handler + 8 行 flag + 5 个测试
- **非侵入**：`--one-shot` 是根级 flag，不影响现有子命令、`-r`/`-c` 等
- **默认安全**：不传 `--one-shot` 时 `args.one_shot is None`，主流 `main()` 完全不走该路径

## 2. 已知不做

- **不暴露内部 agent 参数**：`cmd_one_shot` 使用默认 model 和 max_iterations(90)。进阶配置（model 覆盖等）通过 env 完成。
- **不支持 --model/--provider 联合**：因为 `--model` 在 chat 子 parser 内，不在根 parser。如需可在后续版本加 `--model` 到根 parser，但当前已满足 script/CI 场景。
- **未改 task_runner.py**：保持原有 `run_task` 不变避免回归。`--one-shot` 是轻量独立路径。

## 3. 契约匹配

- 不修改 `SESSION_SEARCH_BACKEND`、`AUTO_EVOLVE` 等 env 默认值
- 不涉及 `data/persistent.json`
- 不修改生产 env
- 不涉及 data 写入
