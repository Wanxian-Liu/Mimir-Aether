# cron 修复 SOP

## 问题模式
Gateway 重启后 cron jobs 的 `next_run_at` 变为 `null`，导致 `get_due_jobs()` 跳过所有任务。

## 修复步骤
1. 读 `cron/jobs.json` 确认所有 job 的 `next_run_at` 状态
2. 手动重算每个 schedule 的 `next_run_at`，不能依赖 croniter（可能不可用）
3. 用 `execute_code` 写回文件（绝对路径 `~/src/MimirAether/cron/jobs.json`）
4. **别在 sandbox 里读盘验证** — sandbox 的 HOME 不同。用 `terminal` 的 `python3 -c "import json; print(...)"` 确认

## 已知的 cron ticker bug
- `cron_mixin.py` 第 794 行 `Path()` 需要 `from pathlib import Path` 导入 — 缺了会在 ticker 里每分钟静默崩溃（`NameError` 被 `logger.exception` 吞掉）
- ticker 异常被 DEBUG 级别日志吞掉 — 应改为 `logger.warning` 以便可见
- 修复后需要 Gateway 重启才生效

## 已知的蒸馏落盘问题
- `dream_memory.py` 的 sandbox expanduser 不一致
- 蒸馏写盘后必须用 `terminal` 读真正路径的 persistent.json 确认
- 真实路径: `~/.mimiraether/data/persistent.json`

## CRITICAL: cron AIAgent vs Script 路径区别

**cron 任务可以通过两种路径执行，API key 行为完全不同：**

| 路径 | 环境 | DEEPSEEK_API_KEY | 能否工作 |
|:----|:----|:----------------|:--------:|
| **AIAgent** (sandbox) | 隔离 sandbox，os.environ 被截断 | *** 或 11 字符 | ❌ 401 |
| **Script** (terminal) | 共享宿主机 /proc | 读 /proc/$PID/environ 或 config.yaml | ✅ 200 |

**关键结论：**
- 任何需要真实 API key 的 cron 任务，如果走 AIAgent 路径且在 sandbox 中执行，必须确保 key 注入机制可靠（/proc 扫描 + provider_registry fallback）
- 可靠方案：cron prompt 调 sync_run_dream_cycle() 让 Agent 在 Gateway 进程内运行，不走 subprocess
- 备用方案：cron script 在 terminal 中从 config.yaml 直接读 key（providers.deepseek.api_key，35字符完整），不走 os.environ 或 /proc

## DEEPSEEK_API_KEY 真源层级（已验证 2026-07-04）

```
1. config.yaml: providers.deepseek.api_key（35字符 sk-...，✅ 可靠真源）
2. Gateway 进程 /proc/$PID/environ（✅ 可靠，但需动态 PID 扫描）
3. os.environ（❌ 被截断为11字符+Unicode占位符）
4. .env 文件（❌ 被显示工具遮盖为 ***）
```

蒸馏脚本必须直接从 config.yaml 读 key，不走 os.environ 或 provider_registry。
已验证：distill_direct.py 从 config.yaml 读 key → 24.2s → 56→17 压缩。
