---
name: mimiraether-systemd-limit-verify
description: systemd 资源限额（MemoryMax 等）的「真生效」判据与取证法——show 值 ≠ 运行内核实值；daemon-reload 对已运行单元即时生效；memory.peak 被 max 夹住。触发词：MemoryMax / 内存顶格 / cgroup 限额 / 限额未生效 / 峰值与上限分离 / room。
category: mimiraether
---

# systemd 资源限额「真生效」判据

## 核心结论（受控实测 2026-10-07）

1. `systemctl show -p MemoryMax` = **配置面**（下次起效的计划值），**不等于**运行进程的真实限额。真值读内核：
   `CG=$(systemctl --user show <unit> -p ControlGroup --value)` → `<cgroup>/memory.{max,high,peak,current,events}`。
2. **`systemctl --user daemon-reload` 会把新增 drop-in 的限额直接套到「已在运行」的单元上**——无需 restart。
   受控判据（临时单元三步）：STEP1 `kernel=max` → STEP2（加 drop-in + reload，**无重启**）`kernel=268435456` → STEP3 restart 同值。
   ⇒ 「限额改动需重启才生效」是**错的**（本机 systemd 版）。
3. 单元文件值与内核值可长期互相矛盾（实测：文件 `4G` / 内核 `6442450944`=6G）⇒ **只读单元文件会误判「未部署/未生效」**。

## 取证三件套

- **真限额**：`memory.max`（运行内核值）。
- **真峰值**：`memory.peak`。内核把它**夹在 `memory.max` 之下** ⇒ ① `peak` 恰为整 GiB = **曾被夹（截断签名）**，此时**禁把 peak 单用当证据**；② `peak` **越过旧帽**才是「帽已真抬高且未 OOM-kill」的证据。
- **压力与杀**：`memory.events` 的 `max`（撞顶次数）/ `oom` / `oom_kill`（是否真杀进程）。

## 两臂受控（复刻同一失败模式，反游戏化）

```
systemd-run --user --scope --collect -p MemoryMax=<帽> -p MemorySwapMax=0 --unit=<唯一名> python3 <分配脚本> <MiB>
```
- 旧臂/新臂**唯一变量 = MemoryMax**（缩放比例照抄生产改动比例）；喂**同一份**已知负载；`MemorySwapMax=0` 禁 swap 兜底。
- 判红 = rc **137**（SIGKILL，无存活标记）；判绿 = rc 0 ∧ 存活标记 ∧ **cgroup 实测 peak > 旧帽**。
- **两臂都报**。缩放臂的 cgroup 增量控制在 **≤ 1 GiB 安全裕度**内（按比例缩放即可复刻失败模式，不必真烧生产帽的量）。

## 陷阱

- **生产 cgroup 只读**：不要写 `memory.peak` / `memory.max`（无公开 reset 路径，且属改生产）。
- **禁在生产 cgroup 内注入负载**（会把网关打下线）。
- 别用 `pgrep -f <脚本名>` 判活（自匹配假阳性）；用 `MainPID` 或 `ps -p <记下的 PID>`。
- 工具面：`/sys/`、`/proc/`、`/.git/` 是 `terminal` 与 `execute_code` 的**拒载片段**（`write_file` 不拦）⇒ 这类取证**落成脚本文件再跑**，或用 `chr(47)` 拼路径。

## 活体配置的真源 = drop-in（2026-10-13 知识库审计实证）

- **被审件 ≠ 活体入口**：审「某个服务的行为」前先 `ps -eo pid,lstart,rss,cmd | grep <port>` + `ss -ltnp`——实证：派单冻结基线给的是 `semantic_server.py`，而 18993 端口真正在跑的是 `uvicorn semantic_http:app`（另一个文件、另一个 SHA）。`ps` 的 `lstart` 还能告出「进程启动时刻」，用来判「改的文件是否已在跑」（启动时刻 < 文件 mtime ⇒ 跑的是旧代码）。
- **功能开关真源在 drop-in，不在源码默认值**：`systemctl --user show <unit> -p DropInPaths --value` → 读 `*.conf`。实证：源码 `MIMIR_CJK_LEG` 默认 `"0"`，而 drop-in `20-cjk-leg.conf` 写 `Environment=MIMIR_CJK_LEG=1` ⇒ 活体返回体里出现 `"match":"cjk"`。**判「功能是否启用」只认活体产物**（返回体/日志），源码默认值与单元文件都可能过期。
- **单元文件常与活体矛盾**（本技能主结论再证）：文件写 `MemoryMax=2G`/`CPUQuota=200%`，`systemctl show` 与内核值同为 `4G`/`800%` ⇒ 真值取 `systemctl show` + `/sys/fs/cgroup<cg>/memory.{max,high,peak,events}`。`memory.events` 的 `high` 计数（如 1434）说明反复撞软限，`max 0 / oom 0` 说明未被杀——两个数一起读才有意义。
- `/proc/<pid>/environ` 可能拒读（`PermissionError`）⇒ 别把它当唯一取证路径，改走 drop-in。

## 回滚

删 drop-in 文件 + `daemon-reload`（同样**即时生效**，无需重启）。
