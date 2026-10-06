# F-1 停机非优雅 · 判据 + 根因 + 修（第 15 单 / A 档 #13）

> 状态：**骨架 v5** —— 根因已从 journal / gateway.log / exit-record 三源锁定到
> 「停机路径跑完后进程不退出」；空闲臂受控复现 `t=0.55s`（判绿）证明基线本就绿
> ⇒ 判据必须带**退不出的载荷臂**。

## 0. 任务口径
F-1「停机非优雅（SIGTERM 超时 → systemd SIGKILL ⇒ 记 failure 才拉起）」→ 做成**可跑判据**（判据 = 停机优雅性）。

## 1. 已确证读数（本 run 自跑）

| # | 对象 | 命令 | 读数 |
|---|---|---|---|
| R1 | unit 关键项 | `cat <unit>` | `TimeoutStopSec=30` · `KillMode=control-group` · `Restart=always` · `RestartPreventExitStatus=78` · `MemoryMax=4G` · `CPUQuota=200%` · `TasksMax=256` |
| R2 | journal SIGKILL 计数 | `journalctl --user -u mimiraether.service --no-pager | grep -c "Killing process.*SIGKILL"` | **65** |
| R3 | journal timeout 计数 | `... | grep -c "Failed with result 'timeout'"` | **45** |
| R4 | 最近一次现场 | `... | grep -B 60 -A 6 "Killing process 369613"` | `18:07:00 Signal SIGTERM received` → `18:07:30 State 'stop-sigterm' timed out. Killing.` → SIGKILL → `Failed with result 'timeout'` |
| R5 | **停机路径真实耗时**（gateway.log） | `grep -n "18:07:0" ~/.mimiraether/logs/gateway.log` | `18:07:00.373 Stopping gateway...` → `.377 [Feishu] Disconnected` → `.378 API server stopped` → **`.380 Gateway stopped`（7 ms 跑完）** → 下一条 `18:07:33.148`（新进程） |
| R6 | exit record | `~/.mimiraether/data/ops/gateway_exit_history.jsonl` 末 6 行 | 18:07:00 行 `active_agents: 0` · `uptime_s 93711.9`（record_exit_event 已在 .380 前写出 ⇒ `_stop_impl` 全跑完） |
| R7 | drain 默认值 | `gateway/restart.py` | `DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT = 60.0`（> 30s，**结构性隐患**，本次未触发） |
| R8 | 生产 config 覆盖 | `grep -n "drain" ~/.mimiraether/config.yaml` | 无输出 ⇒ 走默认 60.0 |
| R9 | **受控复现 · 空闲臂（改前码）** | `python3 scripts/probes/f1_graceful_stop_probe.py --label baseline-idle --port 19499 --assert-secs 10` | **`t=0.55s` · exit 0 · GREEN**（rc=0）⇒ 空闲实例不触发 F-1 |

## 2. 根因（三源锁定）

**根因 = 停机路径跑完后，进程/解释器不退出**（不是停机路径慢）。

证据链：R5（7 ms 内打出 `Gateway stopped`）+ R6（exit record 写出 `active_agents: 0`）+ R4（journal 30 s 无新行 → `stop-sigterm timed out` → SIGKILL）
⇒ 语义 = **停机逻辑已交完作业，进程还在**，systemd 只能 SIGKILL。

候选机制（按嫌疑排序，待实验判别）：

- **M1｜默认 executor 里僵任务**：`asyncio.run` 收尾调 `shutdown_default_executor()`，CPython 对工作线程 join 上限 = **300s** ⇒ 任一 `run_in_executor(None, …)` 作业（embedding / chroma 批处理）没结束，进程就卡在此直到 systemd 30s SIGKILL。
- **M2｜非 daemon 线程**：`threading._shutdown()` join 所有非 daemon 线程。命中创建点：`tools/code_execution_tool.py:874/:1073 rpc_thread`、`:1227 stdout_reader`（**无 join、无超时**）；`gateway/run.py:1259 cron_thread`（有 `join(timeout=5)`，可退）。
- **M3｜asyncio.run 取消残留 task**：`_cancel_all_tasks` 等所有取消完成；task 吞取消（`finally: await …`）⇒ 收尾挂住。
- **M4｜残余子进程**（MCP / browser）⇒ 不阻塞 Python 退出，权重低。

## 3. 停机链（行号 = 盘上真值）

```
SIGTERM → run.py:1216 add_signal_handler → :1201 create_task(runner.stop())
  → session_mixin.py:1281 _stop_task = create_task(_stop_impl)
     ├─ 1164-1178 drain（timeout=默认 60.0；无活跃 agent ⇒ 立即返回）
     ├─ 1188-1197 for adapter: cancel_background_tasks() ; await disconnect()   ← 无超时
     ├─ 1216-1219 clear maps
     ├─ 1220 **self._shutdown_event.set()**
     └─ 1222-1279 尾部清理 + touch clean marker + record_exit_event + log "Gateway stopped"
run.py:1316 await runner.wait_for_shutdown()（只等事件）
  1324-1325 cron_stop.set(); cron_thread.join(timeout=5)
  1328-1330 shutdown_mcp_servers()（同步、无超时）
  1334 raise SystemExit(runner.exit_code)
  ⇒ 之后进入解释器收尾（**F-1 实际卡点**）
```

## 4. 判据清单（可跑 · 待填读数）

- [x] **① 受控复现（空闲臂）**：`t=0.55s` GREEN（R9）
- [ ] **①c 载荷臂**（带「退不出的载荷」的实例）—— 判别臂，两臂对同一判据须一红一绿
- [ ] **② 改后判据**：`t ≤ 10s`（理由：必须 < `TimeoutStopSec=30` 且留 ≥3× 余量）∧ exit ∈ {0} ∧ 停机路径日志齐 ∧ 无 `STOP_BUDGET_EXCEEDED`
- [ ] **③ 非空跑正控**：坏版本（改前码 / 注入僵载荷）喂同一判据 ⇒ 必须判红
- [ ] **④ 生产侧只读**：`Killing process.*SIGKILL` 计数不增读法 + 实测值（本 run 禁 stop/restart/start）
- [ ] **⑤ 根因修 + 回归用例**（`tests/`，禁 skip/xfail，两环境 passed/skipped）

## 5. 待补

1. `run_in_executor(None` 全量扫（M1）+ 非 daemon 线程启动条件（M2）。
2. 载荷臂构造（停机前留下僵 executor 作业 / 非 daemon 线程）。
3. 修 + 回归用例 + 两臂读数。

---
（骨架 v5）
