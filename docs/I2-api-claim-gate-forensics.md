# I-2 取证笔记 · api 直连通道与 watcher 共用认领闸

> 状态：**取证中**（骨架 + 已确证部分 + 待补清单）
> 单号：第 21 单 · I-2

## 1. 任务（要点）
让 `POST /v1/runs`（api 直连通道）与 watcher 认领走**同一套机器闸**（claim/幂等），
根治「同一单被认领两次」。

## 2. 实证（L2 复核读数 · 非推测）
- 2026-10-07 **03:36:17** api 投第 8 单
- 2026-10-07 **03:50:01** watcher 对第 44 行 `RESERVE prev_dispatched=43 -> COMMIT`
- => 同一单重复唤醒一次（第 2 路 run）
- 根因：claim 闸只在 watcher 侧；api 通道对它透明（契约层约定，非机器强制）

## 3. 已确证（盘上读数）
| 项 | 读数 | 备注 |
|---|---|---|
| api 入口 | `gateway/platforms/api_server.py:1609 _handle_runs` | 路由注册 `:1875` |
| claim 实现 | `~/.mimiraether/scripts/buzz_inbox_claim.py`（363 行） | 2026-10-07 T7-F1 已建 |
| watcher | `~/.mimiraether/scripts/buzz-inbox-watcher.sh`（125 行） | |
| claim 台账 | `~/.openclaw/data/buzz-inbox-mimir.dispatched.claim.log` | 含 prev_dispatched= |
| 回归用例 | `tests/gateway/test_buzz_watcher_ledger.py`（198 行） | 已存在 |

### 3.1 claim 脚本已读结论（buzz_inbox_claim.py 头注逐字）
- 问题原文：「同一派单行（信箱游标 42）被两个 run 并行消费——run 9f313cb9
  （trigger_source=api，02:44:41→03:07:21）与 run 5ee412bb（trigger_source=buzz-watcher）」
- 「根因 = 消费侧『读取』与『推进游标』之间无原子认领步（watcher 全序列无 flock；
  唯一"锁"是派发之后才创建的存在性文件 => TOCTOU 窗口 = 整段决策+派发耗时）」
- 子命令：reserve / abort / commit / check / show
  - `check`：0=可碰 / 2=他人持有 / 3=已处理
  - `reserve`：认领 [start,end] 并原子抬 dispatched=end
  - 并发语义：flock 独占（跨进程）；同一行只能被一个 owner 认领
  - 另有 TAKEOVER（ttl-expired 接管）
=> **闸已存在且语义完备**；缺口只在「api 通道不走它」。

## 4. 待补清单
- [ ] 读 api_server.py `_handle_runs` 全文 -> api 通道当前是否触碰 claim
- [ ] 读 watcher.sh -> claim 调用点与参数
- [ ] 定位 api 投递与 watcher 认领的**共用信封标识**（行号 / 单号 / trace_id）
- [ ] 改前臂受控复现（必须复现重复唤醒，两 run 读数）
- [ ] 改后臂（第二次被机器拒 + 可见读数，禁静默）
- [ ] 回归用例 >=1（禁 skip/xfail，两环境跑，报 passed/skipped）
- [ ] 标注三处（代码注释 / docs 一节含「闸拒时看什么读数」/ 台账一行）
- [ ] §14 安全重启 + post_restart_verify.py VERDICT + next_run_at 重算

## 5. 根因确证（2026-10-07 盘上读数）

**派单方脚本**：`/home/rayliu/.hermes/scripts/mimir-send.sh`（头注逐字）：
> 「给 Mimir 发单 = 邮箱留档 + API 立刻唤醒（刘哥 2026-10-05 定 · 升级版）」
> 「原版（2026-08-18 刘哥定）：只走 API 直连 18999/v1/runs——秒到但不留档」
> 「现版：先写邮箱（六键信封）再唤醒——信留档；万一它没跑，watcher（≤5min）会自己取」

⇒ **两条通道消费同一信封**：`mimir-send.sh` 写 `buzz-inbox-mimir.jsonl` 一行（第 44 行）
   + 立刻 `POST /v1/runs`；watcher 每 5min 看同一文件的行数 vs `dispatched`。

**api 侧不触碰 claim**（grep 读数）：
- `gateway/platforms/api_server.py:1608 _handle_runs` 全文无 claim 调用（只做 auth /
  并发上限 / body 解析 / 建 run / `begin_run`）
- 全仓 `grep -rn 'buzz_inbox_claim'` 命中 = 仅 watcher.sh + claim 自身 + selftest

**watcher 侧读数（claim 台账）**：
```
2026-10-07 03:50:01 RESERVE owner=watcher-3048865-1791316201 range=44..44 prev_dispatched=43
2026-10-07 03:50:01 COMMIT  owner=watcher-3048865-1791316201 range=44..44
```
⇒ `prev_dispatched=43` 证明 api 投递（03:36:17）**没有推进 dispatched**，
   于是 watcher 把第 44 行当新行再认领一次 = 重复唤醒。

**结构根因（两条、各自充分 · 与 INC-12 同源）**：
1. claim 闸只在 watcher 侧；api 通道对它透明（契约层约定，非机器强制）
2. `wake_gate.py:108 WAKE_TRIGGER_SOURCES` 不含裸 `api` ⇒ api 唤醒判 `mode="user"`
   放行且不占位；且 `/v1/runs` 的 `session_key` = 该 run 自身 trace_id ⇒ 去重键恒不同

## 6. 上闸设计（方案）
**核心**：让 api 通道在**唤醒前**对「它要处理的那一行」做同一套 claim（`reserve`），
watcher 随后到 ⇒ 同一行已被 dispatched 覆盖 ⇒ `reserve` 返 rc=1（无增量）或 rc=2（HELD）
⇒ 机器拒，且**出声**（claim 台账行 + stderr）。

**信封 → 行号绑定**：`mimir-send.sh` 写行时拿 `wc -l` 得行号，把 `inbox_line` 放进
`POST /v1/runs` 的 `metadata`；api 侧读 `metadata.inbox_line` ⇒ 对该行 `check` + `reserve`。

**边界（已知）**：
- 只挡「同一信封被两条通道各唤醒一次」；**不挡**同一信封在单通道内被重复处理
- 只对**带 `inbox_line` 的 api 唤醒**生效；不带该字段的 api 调用（用户直接 /v1/runs）
  不受影响（保持原行为）
- 若 api 侧 reserve 后 run 崩溃，TTL(300s) 后 watcher 可接管（不死信）

## 7. 上闸落点（本次改动 · 3 个文件）

| 文件 | 角色 | 改动 |
|---|---|---|
| `gateway/inbox_claim_gate.py`（新） | 闸本体（api 侧） | 三态决策 + 台账 + 认领器调用 |
| `gateway/platforms/api_server.py` | 接线点 | `_handle_runs` 建 run 之前调用；被拒返 409；受理后 `commit` |
| `~/.hermes/scripts/mimir-send.sh` | 派单方 | 唤醒时带 `metadata.inbox_line`（**增量**字段，格式向后兼容） |

## 8. 闸的语义 · 边界 · 失效条件（标注）

### 8.1 语义（三态可判，禁静默）

| 状态 | 触发 | api 侧动作 | 可见读数 |
|---|---|---|---|
| `issued` | 认领器 rc=0 | 放行 run；受理后 commit | 日志 `[inbox_claim_gate] ISSUED` + 台账 `event=issued` + 共享 `RESERVE` 行 |
| `rejected` | rc=1 无增量 / rc=2 HELD | **HTTP 409**（`code=inbox_line_already_claimed`） | 日志 `REJECTED` + 台账 `event=rejected`（带 rc/reason）+ 共享 `HELD` 行 |
| `degraded` | 认领器缺失 / rc=3 / 输出不可解析 | **放行**（闸故障不停摆） | 日志 `DEGRADED` + 台账 `event=degraded`（带 detail） |

**闸拒时看什么读数**（四条，任一条可独立复核）：
1. `~/.mimiraether/data/ops/api_claim_gate.jsonl` —— `event=rejected` 行（run_id / declared / rc / reason）
2. `<dispatched>.claim.log` —— 共享认领台账的 `RESERVE` / `HELD` / `COMMIT` 行
3. HTTP 响应体 —— 409 + `code=inbox_line_already_claimed` + `state= rejected ...`
4. `python3 ~/.mimiraether/scripts/buzz_inbox_claim.py show` —— 三游标 + 当前 claim

### 8.2 边界（已知 · 别当万灵药）

- **只挡「重复认领」**：同一封信封被两条通道各唤醒一次。
- **不挡**：① 同一信封在**单通道内**被重复处理；② watcher 自身重跑（门控在 watcher 侧原有）；
  ③ TTL(300s) 过期接管后的二次进入 —— 接管是**有意**的（保不死信），取舍见 8.3。
- **不挡**「内容相同但行号不同」的两封信：闸的幂等键是**行号区间**，不是信封内容摘要。
- 只对带 `metadata.inbox_line` 的请求生效；不带该字段 = 用户/前端直连调用，不触碰 claim。

### 8.3 失效条件（何时这台闸会 hold 不住）

1. **派单方不带 `inbox_line`** ⇒ 退化为「无闸」（`state=none`）。这是本闸的**唯一入口假设**，
   也是本次同时改 `mimir-send.sh` 的原因（只改 api 侧 = 只上锁、不给钥匙）。
2. **`BUZZ_INBOX_MIMIR*` 两侧指向不同文件**（如沙箱覆写漏键）⇒ 各认领各的，互不相识
   —— 本次 harness 自身就踩过一次（见 §9 事故）。
3. **认领器路径不一致**（`BUZZ_INBOX_MIMIR_CLAIM_TOOL` 与 watcher 默认值背离）⇒ 同上。
4. TTL 窗口内 run 崩溃 ⇒ 区间由 watcher 在 TTL 后接管：**可能二次执行**（这是「不死信」的代价，
   与「重复唤醒」是两回事：前者是保送达，后者是资源浪费）。若未来要收紧，需在 run 侧加
   「已完成」标记，而不是缩 TTL。

### 8.4 为什么不新增第三个状态机

`claim.json` + `dispatched` 游标已是两通道**唯一的共享幂等状态**；新增状态 = 新增不一致面。
本闸只做一件事：把 api 侧接进既有 flock 关键区。

## 9. 事故记录（本人 · 2026-10-07 09:27:49）

两臂 harness 首版只覆写了闸台账路径、漏覆写 `BUZZ_INBOX_MIMIR_DISPATCHED`
⇒ 认领器打到**生产**收件箱：`RESERVE owner=api-run_harness_b range=59..59 prev_dispatched=58`
→ 把第 59 行标成已派发（**静默丢信**风险）。已回滚 `dispatched 59->58` 并在共享台账追加
`INCIDENT-ROLLBACK` 行；harness 加 `_assert_sandbox()` 护栏（非 `/tmp/` 拒跑）。
教训：**覆写「一部分」env ≠ 隔离**——脚本里每个 `${VAR:-默认}` 都是真实路径。
（同族先例：`tests/gateway/test_buzz_watcher_ledger.py` 头注 G2 勘误。本仓新用例 fixture 已覆写全部键。）

## 10. 段界交棒（B3 · 落盘时点读数）

### 已完成（含读数）
| 项 | 读数 |
|---|---|
| 根因确证 | `mimir-send.sh` 写箱+api 双路；api 侧零 claim 调用（grep 命中=仅 watcher） |
| 改前臂 Arm A | 同一信封 **唤醒=2**（重复唤醒复现） |
| 改后臂 Arm B | 同一信封 **唤醒=1**（第二次被机器拒）· `VERDICT PASS` |
| 闸语义 | 三态 issued/rejected/degraded；拒时 409 + 台账行（非静默） |
| 回归用例 | `test_i2_api_claim_gate.py` **18 passed / 0 skipped / 0 xfail** ×2 环境（.venv 3.12 + .venv.bak-3.11.15） |
| 投递行为不变 | `mimir-send.sh` E2E：**2/2** 投递成功，`input` 原样，`metadata.inbox_line` 递增 |
| 标注 | 代码注释（模块头 + api_server 接线点）· docs §8 · skill 三副本 · 台账行 |

### 未闭项（下一段第一件事）
1. **运行生效**：gateway 需重启才装载新 `api_server`（当前进程仍是旧码）——
   走 §14 安全姿势（`systemd-run --user --unit=... --collect` 独立 cgroup）；
   重启后跑 `scripts/post_restart_verify.py` 取 `VERDICT`，并按 §14 重算空 `next_run_at`。
2. 回执落盘 `~/.hermes/inbox/`（附三件套 + 两字段）。
3. 生产首单自证：等下一次 `mimir-send.sh` 投递，读
   `~/.mimiraether/data/ops/api_claim_gate.jsonl` 应出现 `event=issued`，
   且 5min 内 watcher 不再为同一行 `RESERVE`。

### 已知风险（整改预备）
- 重启窗口内 gateway 内存 4.0G / 帽 6G（room≈2G）⇒ 若 OOM，按 §14 记录
  `Failed with result 'oom-kill'` 并回滚本次 commit。

重跑命令: python3 /home/rayliu/.mimiraether/scripts/i2_two_arm_harness.py
复算数字: Arm A 唤醒=2 / Arm B 唤醒=1 / VERDICT=PASS
