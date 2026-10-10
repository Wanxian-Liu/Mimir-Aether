# F-1 停机非优雅 · 判据 + 根因 + 修（第 15 单 / A 档 #13）

> 状态：**终版**（判据可跑 · 两臂一红一绿 · 根因点名到代码路径 · 修已落盘 + 用例 + 需重启才生效）

## 0. 结论摘要（三句）

1. **判据成立**：改前同判据判红（payload 臂 `t=35.01s` 被强杀 `exit=-9`），改后判绿（`t=20.03s` `exit=0`）。
2. **根因**：不是停机逻辑慢 —— 停机路径 **7 ms 就跑完**（`18:07:00.373 → .380`）；卡点在**停机之后的解释器收尾**：`asyncio.run()` 的 `Runner.close()` 会 join 默认 executor 的工作线程（CPython 上限 300s），而生产里 **API `POST /v1/runs` 把 agent run 丢进默认 executor**（18:03:11 `run_d075d5ac`），stop 时它既不被 drain 计数也不被打断 ⇒ 进程活到 systemd `TimeoutStopSec=30` 被 SIGKILL，记 `Failed with result 'timeout'`。
3. **修**：给整条停机尾链一个硬上限（退出看门狗，默认 20s < systemd 30s），到点落线程栈 + 出声 + 以原意退出码 `os._exit`；并把 drain 默认 60s 夹进该预算（`60.0s → 12.0s`）。

## 1. 判据（可跑 · 绿/红语义）

命令（受控实例 · 独立端口 19499 + 临时 `MIMIR_AETHER_HOME` · **不碰生产网关**）：

- 空闲臂：`python3 scripts/probes/f1_graceful_stop_probe.py --label <L> --port 19499 --assert-secs 10`
- 载荷臂：`… --label <L> --port 19499 --assert-secs 25 --kill-wait-secs 35 --inject-executor-stall`

过闸（全绿才 GREEN，rc=0）：

| 检查 | 语义 |
|---|---|
| `t_within_assert` | `t = SIGTERM→进程消失` ≤ 阈值（空闲 10s / 载荷 25s），且**未被探针强杀** |
| `exit_code_allowed` | 退出码 ∈ {0}（**非 -9**：-9 = 被 SIGKILL） |
| `stop_path_logged` | 日志有 `Signal SIGTERM received` **且**（`Gateway stopped` 或 clean marker） |
| `no_bad_markers` | 无 `drain timed out` / 无 `STOP_BUDGET_EXCEEDED` |

阈值理由（绝对口径，禁「比改前快」）：systemd 给的是 `TimeoutStopSec=30`；判据阈值必须**严格小于**它并留余量 ⇒ 空闲臂 10s（30s 的 1/3）、载荷臂 25s（余 5s）。改后生产默认看门狗 20s（余 10s）。

## 2. 两臂读数（改前 `cdce26b` / 改后 `bc176ed`，同判据同实验）

| 臂 | 改前 | 改后 |
|---|---|---|
| 空闲（无载荷） | `t=0.60s` · exit 0 · **GREEN**（rc=0） | `t=0.50s` · exit 0 · **GREEN**（rc=0） |
| 载荷（默认 executor 里有在飞作业） | **`t=35.01s` · exit -9（被 SIGKILL）· RED**（rc=1） | **`t=20.03s` · exit 0 · GREEN**（rc=0） |

③ **非空跑正控**：同一判据在坏版本上**判红**（`t_within_assert=false` ∧ `exit_code_allowed=false` ∧ `force_killed_by_probe=true`）⇒ 判据有牙，不是恒绿。

改后证据（载荷臂 sandbox 日志原文）：

```
WARNING gateway.session_mixin: F1: drain budget clamped 60.0s -> 12.0s (exit watchdog 20.0s)
ERROR __main__: F1_EXIT_WATCHDOG_FIRED trigger=signal:SIGTERM after=20.0s threads=5 exit_code=0 \
  stacks=/tmp/f1-sandbox-ju60kz9p/logs/stack-dumps/exit-watchdog-1791321934.log \
  — forced exit before systemd TimeoutStopSec
```


## 3. 根因与证据链

| # | 证据（原文/读数） | 排除/支持 |
|---|---|---|
| E1 | `journalctl … \| grep -B60 -A6 "Killing process 369613"` ⇒ `18:07:00 Signal SIGTERM received` → **30s 无任何行** → `18:07:30 State 'stop-sigterm' timed out. Killing.` → SIGKILL → `Failed with result 'timeout'` | 现象 |
| E2 | `grep -n "18:07:0" ~/.mimiraether/logs/gateway.log` ⇒ `.373 Stopping gateway...` → `.377 [Feishu] Disconnected` → `.378 API server stopped` → **`.380 Gateway stopped`** | **排除「停机逻辑慢」**：停机路径 7 ms 跑完 |
| E3 | `data/ops/gateway_exit_history.jsonl` 18:07:00 行 ⇒ `active_agents: 0`（record 由 `_stop_impl` 尾部写出） | **排除 drain 慢**（本次无活跃 agent） |
| E4 | `logs/gateway-api.log` 18:03:11 ⇒ `POST /v1/runs` … `run_d075d5ac…`（即 18:04–18:06 活动的 b8649222） | **点名在飞作业**：API run 在停机时仍在跑 |
| E5 | `gateway/platforms/api_server.py:1558/:1743` ⇒ `run_in_executor(None, _run / _run_sync)` | 该 run **跑在默认 executor 里**，且 `_running_agents` 不含它 ⇒ drain 既不计数也不打断 |
| E6 | 全仓扫 `threading.Thread(` 带括号配对 ⇒ **0 个缺 `daemon=`**；MCP 关停有 `join(timeout=5)` / `future.result(timeout=15)` | **排除 M2（非 daemon 线程）/ M5（MCP 关停）** |
| E7 | 改后强杀点自查：看门狗落栈首帧 = `asyncio/runners.py:194 run → :62 __exit__ → self.close()` | **坐实 M1**：卡在 `asyncio.run` 收尾（join 默认 executor，CPython 上限 300s） |

⇒ **根因（一句话）**：`TimeoutStopSec` 是**整进程**的预算，而停机链只给「停机逻辑」设了预算；停机逻辑之后的**解释器收尾无界**（默认 executor join ≤300s），且 stop 时在飞的 API run 既不被 drain 计数也不被打断 ⇒ systemd 只能 SIGKILL，全部被记成 failure。

## 4. 修（只动停机路径）

| 文件 | 改动 |
|---|---|
| `gateway/exit_watchdog.py`（新 · 6.8 KB） | 退出看门狗：默认 20s（`MIMIR_EXIT_WATCHDOG_SECS` 可调，**夹在 [1, 29]**，永不许 ≥ systemd 30s）；纯函数 `exit_watchdog_seconds()` / `drain_budget_seconds()` 与副作用 `arm_exit_watchdog()` 分离；到点：落线程栈 → `ERROR F1_EXIT_WATCHDOG_FIRED` → `logging.&#8203;shutdown()` 刷新 → `os._exit(exit_code)`（沿用意图码，如 service restart 的 75） |
| `gateway/run.py` | SIGTERM/SIGINT handler（`:1201` 前）与 SIGUSR1 restart handler 内**武装看门狗**（best-effort，装不上不影响停机） |
| `gateway/session_mixin.py` `_stop_impl` | `drain` 由 `self._restart_drain_timeout`（默认 **60s**）**夹进**看门狗预算：`60.0s → 12.0s`（watchdog 20 − margin 8），并 `WARNING` 出声 |
| `tests/test_f1_exit_watchdog.py`（新） | 6 用例：默认 < 30s · env 夹取 · 非法值回落 · drain 夹取（不为负）· **子进程验证真退出**（耗时≈上限 ∧ 退出码取 provider ∧ 出声）· status 可观测 |

## 5. 生产侧只读读数（④）

```
重跑命令: journalctl --user -u mimiraether.service --no-pager | grep -c "Killing process.*SIGKILL"
复算数字: 65（本 run 实测；与派单前一致 ⇒ 不增）
```
本 run **未**执行任何 `systemctl --user stop|restart|start mimiraether`（生产网关 PID 未变，仍为在跑原进程）。

## 6. 用例（两环境）

| 环境 | 命令 | 读数 |
|---|---|---|
| 改后（主树） | `.venv/bin/python3 -m pytest tests/test_f1_exit_watchdog.py -q` | **6 passed · 0 skipped · 0 failed**（3.36s） |
| 改前（worktree `cdce26b`） | 同命令（把用例拷进 worktree） | **1 error（collection：无 `gateway.exit_watchdog`）· 0 passed** ⇒ 单元级 RED 臂 |

## 7. 边界（改了 / 未动）

- **改了**：`gateway/exit_watchdog.py`（新）· `gateway/run.py` · `gateway/session_mixin.py` · `tests/test_f1_exit_watchdog.py`（新）· `scripts/probes/f1_graceful_stop_probe.py`（新）· `docs/reports/F1-graceful-stop.md` · 台账/回执。
- **未动**：systemd unit（`TimeoutStopSec` 等一字未改）· 生产进程（未 stop/restart/start）· `tools/mcp_tool.py` · adapter 实现 · 清单条目与口径 · 他方文件（`skills/…SKILL.md` 的改动**非本 run**）。

## 8. 角色帽三件套（§2.3 · 本单件型 = 停机/可靠性 ⇒ 基座帽）

- **角色**：SRE (Site Reliability Engineer) 🛡️
- **卡路径**：`~/wiki/raw/agency-agents/engineering/engineering-sre.md`（真源 3822 B · 本次全文重读）；索引卡 `~/wiki/concepts/角色-engineering-Sre.md`
- **引用规则（逐字原文）**：
  - `引用规则1: **Measure before optimizing** — No reliability work without data showing the problem`（先取 E1–E4 读数再动手，不修症状）
  - `引用规则2: **Blameless culture** — Systems fail, not people. Fix the system.`（修机制：看门狗，而非追「谁没退出」）
  - `引用规则3: **Progressive rollouts** — Canary → percentage → full. Never big-bang deploys.`（⇒ 需重启才生效的改动**只报不动**，交刘哥排窗口）
  - `引用规则4: **SLOs drive decisions** — If there's error budget remaining, ship features. If not, fix reliability.`
- **用到的方法段**：`🔧 Critical Rules`（1–5）· `🔭 Observability Stack / The Three Pillars`（Logs = 「What happened at 14:32:07?」= E1/E2 时点对齐）· `🔥 Incident Response Integration`（`Post-incident reviews focused on systemic fixes`）

## 9. 需重启才生效（按 §8.2 出口闸：本 run 不发完工宣称）

看门狗是**进程内**设施 ⇒ 生产网关**重启后**才生效。本 run **只报不动**。

## 10. 待跟进（不在本单范围 · 只记录）

1. `api_server` 起的 run **未纳入 `_running_agents`** ⇒ drain 不计数、不打断（E4/E5）。修它属「run 生命周期」而非「停机路径」，未动。
2. `DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT = 60.0` 大于 systemd 30s 是**默认值层面的隐患**（本单只做夹取，未改默认值 —— 改默认值会影响 restart 语义，需另裁）。
