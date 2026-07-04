# cron 修复 SOP

## 问题模式
Gateway 重启后 cron jobs 的 `next_run_at` 变为 `null`，导致 `get_due_jobs()` 跳过所有任务。

## 修复步骤
1. 读 `cron/jobs.json` 确认所有 job 的 `next_run_at` 状态
2. 手动重算每个 schedule 的 `next_run_at`，不能依赖 croniter（可能不可用）
3. 用 `execute_code` 写回文件（绝对路径 `/home/rayliu/src/MimirAether/cron/jobs.json`）
4. **别在 sandbox 里读盘验证** — sandbox 的 HOME 不同。用 `terminal` 的 `python3 -c "import json; print(...)"` 确认

## 已知的 cron ticker bug
- `cron_mixin.py` 第 794 行 `Path()` 需要 `from pathlib import Path` 导入 — 缺了会在 ticker 里每分钟静默崩溃（`NameError` 被 `logger.exception` 吞掉）
- ticker 异常被 DEBUG 级别日志吞掉 — 应改为 `logger.warning` 以便可见
- 修复后需要 Gateway 重启才生效

## 已知的蒸馏落盘问题
- `dream_memory.py` 的 sandbox expanduser 不一致
- 蒸馏写盘后必须用 `terminal` 读真正路径的 persistent.json 确认
- 真实路径: `/home/rayliu/.mimiraether/data/persistent.json`
