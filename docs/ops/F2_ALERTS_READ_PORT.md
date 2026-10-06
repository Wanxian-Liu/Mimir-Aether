# F2 · alerts 读口（跨通道出声通道）

**任务**：全清任务清单 #2 / 第 8 单 · 派单方 Hermes（RealityChecker 🧐）
**件型**：告警 / 可观测 ⇒ 基座帽 SRE 🛡️（Golden Signals · 错误语义不可裁剪）

## 病灶（盘上实证）
`agent/run_health.py`（生产端）越线时 append `data/ops/run_health_alerts.jsonl`，
但**无任何非本模块消费者** ⇒ 「只写字段、无人被告知」：阈值越线只落一行 jsonl，
外部要发现它必须**人工打开 jsonl** ⇒ 出声面不成立。
（读数：`grep -rln 'run_health_alerts' --include=*.py .` 仅命中生产端 + 其单测。）

## 交付（复用现成机制 · 不新造系统）
| 件 | 路径 | 作用 |
|---|---|---|
| 读口脚本 | `scripts/check_run_health_alerts.py` | 独立消费者：读 alerts jsonl ⇒ stdout 明示 + rc 语义 |
| 跨通道接入 | `run_ralph_tier0.sh`（Gate1） | tier0 输出出现 `RUN_HEALTH_ALERTS:` 行 ⇒ 不再依赖人工开文件 |
| 正负控 | `tests/scripts/test_check_run_health_alerts.py`（16 例） | 坏样本必出声 ∧ 好样本不误拦（无 skip/xfail） |
| 自证 | `scripts/check_run_health_alerts.py --selftest` | 5 坏病例 + 4 孪生对照 + 1 非静默 |

同族先例：`scripts/check_cron_hygiene.py`（同样接进 Gate1 + `--selftest` + tests/scripts 回归）。

## rc 语义（错误语义不可裁剪：各态可分辨）
| state | rc | 触发 |
|---|---|---|
| `NONE` | 0 | 台账在盘、窗口内 0 条 —— **明示**「无告警」（禁空白静默） |
| `ALERT` | 2 | 有告警（n / latest / by_kind 三行） |
| `MISSING` | 3 | 台账缺失且 state 证明「已 fire 过」或 state 也缺 ⇒ 出声通路断了 |
| `UNREADABLE` | 3 | 权限 / IO |
| `PARSE_ERROR` | 4 | 坏行 > 0（仍列出已解析部分，禁「一坏全隐」） |
| `NO_ALERTS_YET` | 0 | 台账缺但 state 在盘且**从未** fire ⇒ 合法（防假红） |
| `SKIP` | 0 | home 目录不存在 ⇒ 非 Mimir 主机（CI）⇒ 不假红 |

`--gate`（tier0 用）：只对「通路故障」（MISSING / UNREADABLE / PARSE_ERROR）非 0；
`ALERT` 照常打印但不判死 —— 否则一条告警会让 Gate1 永久红（红久必被绕过，等于没闸）。

## 判据（DoD 逐条）
① 有读口：`git ls-files scripts/check_run_health_alerts.py run_ralph_tier0.sh` 均命中；
`grep -rln 'run_health_alerts' --include=*.py .` 现含**非生产端**消费者。
② 阈值触发时外部可读：默认模式 rc=2 + stdout 行（不依赖人工打开 jsonl）。

## 回滚
删 `scripts/check_run_health_alerts.py` + 测试文件 + `run_ralph_tier0.sh` 内本段
（读口本身纯只读：不写盘、不改 state、不发网络、不 import `agent.run_health`）。

## 残余缺口（不静默）
- `ALERT` 在 tier0 下 rc=0（**刻意**）：告警的「判死」通道是默认模式 rc=2，由调用方决定是否升级。
- 读口是**拉**模式（pull）：无主动推送（飞书 / Buzz）。要推需新通道 + 限流 ⇒ 另单，本单不做。
