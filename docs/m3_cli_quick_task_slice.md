# M3 垂直切片：CLI 单次任务（`-q`）

## 场景

用户在仓库根执行：

```bash
python cli.py -q "任务描述" [--model MODEL] [--max-iterations N]
```

解析后进入 `cli.main()` → `asyncio.run(run_task(...))` → `MimirAetherAgent.run_conversation`。

## 自动化验收（无网、桩 LLM）

测试文件：`agent/test_m3_cli_quick_task_slice.py`

- 直接调用 **`cli.run_task`**（与子进程 `python cli.py -q ...` 同栈，避免 shell/PTY 差异）。
- 对 **`MimirAetherAgent._call_model_with_tokens`** 打桩，校验 stdout 中出现桩回复与用户任务片段。
- Checkpoint 目录隔离到 pytest `tmp_path`。

运行：

```bash
python3 -m pytest -q agent/test_m3_cli_quick_task_slice.py
```

纳入默认门禁：`./run_ralph_tier0.sh`（Gate2 列表）。

## 与里程碑 A / M3 的关系

- **里程碑 A**「能跑通一条用户可感知的 CLI 任务」：本子切片覆盖 **代码路径**；真网、真 key、真模型需在 **smoke 清单**（如 `docs/mimir_prod_smoke.md`，待补）中单独勾选。
- **M3**：本仓库第一条固定 **入口 + 断言** 的垂直切片；后续可增第二条（如 `api_service` + TestClient）。

## 修订

| 日期 | 说明 |
|------|------|
| 2026-05-01 | 初版：run_task + 桩 LLM + Ralph Gate2。 |
