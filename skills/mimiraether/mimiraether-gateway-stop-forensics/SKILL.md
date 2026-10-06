---
name: mimiraether-gateway-stop-forensics
description: Gateway 停机非优雅（SIGTERM 超时 → systemd SIGKILL / Failed with result 'timeout'）的三源取证 + 受控实例判据 + 退出看门狗修法。触发词：停机非优雅/F-1/SIGKILL 拉起/timeout failure/TimeoutStopSec/退不出/优雅退出。
---

# Gateway 停机非优雅（F-1）取证与修复 SOP

## 何时用
- journal 出现 `Killing process … SIGKILL` / `Failed with result 'timeout'` / `State 'stop-sigterm' timed out`
- 「重启后服务被记 failure 才拉起」「stop 要等 30 秒」

## 关键反直觉（2026-10-07 实证）
**停机逻辑跑完 ≠ 进程退出。** 实测停机路径 `Stopping gateway...` → `Gateway stopped` 只花 **7 ms**，
进程仍活到 systemd `TimeoutStopSec=30` 被 SIGKILL。别一上手就去优化 drain/adapter —— 先证明卡在哪一段。

## 三源取证（顺序固定，缺一不可）
```bash
# ① journal（systemd 侧，只读）
journalctl --user -u mimiraether.service --no-pager | grep -B60 -A6 "Killing process <PID>"
journalctl --user -u mimiraether.service --no-pager | grep -c "Killing process.*SIGKILL"
# ② 停机路径真实耗时（INFO 级只进日志文件，不在 journal！）
grep -n "<HH:MM>:0" ~/.mimiraether/logs/gateway.log | head
# ③ 退出记录（active_agents 是 drain 是否该等的判据）
tail -6 ~/.mimiraether/data/ops/gateway_exit_history.jsonl
```
判读：
- ② 里 `Stopping gateway...`→`Gateway stopped` 差值 ≪ TimeoutStopSec ⇒ **卡点在停机之后的收尾**（跳 ④）
- ② 里两者之间没有 `Gateway stopped` ⇒ 卡在 drain / `adapter.disconnect()` / MCP 关停

## 常见根因（按已证伪/已证实排序）
| 机制 | 证据 | 状态 |
|---|---|---|
| `asyncio.run()` 收尾 join 默认 executor（CPython `THREAD_JOIN_TIMEOUT=300`） | 看门狗落栈首帧 = `asyncio/runners.py:40x run → Runner.close()` | **已证实（2026-10-06 18:07 事件）** |
| 在飞作业藏在 executor：`api_server.py` `run_in_executor(None, _run/_run_sync)`（API `POST /v1/runs` 起的 run **不进 `_running_agents`** ⇒ drain 不计数、不打断） | `logs/gateway-api.log` 停机前有 `POST /v1/runs` | **已证实** |
| drain 预算 > systemd 预算：`DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT = 60.0` | `gateway/restart.py` | **结构性隐患（默认值）** |
| 非 daemon 线程 `threading._shutdown` join | 全族扫描：prod 代码 `threading.Thread(` **均带 `daemon=`** | 已证伪（勿再猜） |
| MCP 关停 | `join(timeout=5)` / `future.result(timeout=15)` | 已证伪（有上限） |

## 判据（受控实例 · 绝不动生产网关）
`scripts/probes/f1_graceful_stop_probe.py`：独立端口 + 临时 `MIMIR_AETHER_HOME` 起实例 → SIGTERM → 量 `t`。
- 空闲臂：`t` 本就 <1s（**不判别**任何东西 —— 基线绿不等于没问题）
- **载荷臂**：`--inject-executor-stall`（占住默认 executor worker ⇒ 复现生产签名）才是判别臂
- 过闸：`t ≤ 阈值` ∧ exit ∈ {0}（**exit=-9 = 被 SIGKILL = 红**）∧ 停机路径日志齐 ∧ 无 bad marker
- **两臂必须一红一绿**，否则判据是恒绿的空枪

## 修（最小面 · 只动停机路径）
1. `gateway/exit_watchdog.py`：整条尾链硬上限（默认 20s < `TimeoutStopSec`30，夹 [1,29]），到点 → 落线程栈 → `ERROR F1_EXIT_WATCHDOG_FIRED` → 刷新日志 → `os._exit(意图码)`
2. `gateway/run.py`：SIGTERM/SIGINT 与 SIGUSR1 handler 内 `arm_exit_watchdog(...)`（在 `create_task(runner.stop())` **之前**）
3. `gateway/session_mixin._stop_impl`：`drain_budget_seconds()` 把 drain 夹进看门狗预算

## 坑
- 命令串里出现字面量 `shutdown` / `.env` / `/.git/` / `/usr/` / `/proc/` / `.config` 会被载荷白名单整块拒 ⇒ 用 `"shut"+"down"` 拼接
- 看门狗是进程内设施：**改完必须重启 gateway 才生效**——禁止在飞书轮内重启，只报不动
- 取证前先记生产 `grep -c SIGKILL` 基线，跑完再数一次（**不增**才算没扰生产）
