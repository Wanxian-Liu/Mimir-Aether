# Mimir 自主守护进程套件

## ⚠️ 2026-08-18 重大更新：方案已修正（P1 排查实证）

**`scripts/mimir-daemon.py`（18791 端口）已 DEPRECATED**——文件头明示 "Port 18999 is the real Gateway. This daemon is no longer needed"，它只是 HTTP 状态服务器，**不扫描讨论室、不处理卡**。按本技能旧"三步部署"执行 = 部署一个无用的状态服务，**不能修复自主接管**（2026-08-18 P1 实证）。

**真正的自主接管链路 = wiki-watcher cron job 的执行环节**（2026-08-18 已修复）：

## 正确方案（已落地 · 2026-08-18）

### 根因（曾导致"只检测不执行"）

`gateway/cron_mixin.py` `execute_cron_job`（L795）：job 有 `script` 字段时**只跑 script**，script stdout 直接成为交付物，**`job.prompt` 从不进入 agent 循环**（agent 分支 L831 仅无 script 时执行）。

### 修复动作

1. `cronjob action=update job_id=<wiki-watcher id> script=""` **清空 script 字段**（jobs.json 中 `"script": null`）→ prompt 走 fresh AIAgent 分支
2. prompt 用 WHERE-WHAT-HOW 结构 + 无卡时输出 `[SILENT]`（`cron_mixin.py` L864 检测到 `[SILENT]` 即跳过交付，零消耗）
3. **无需重启 gateway**：`cron/jobs.py` `load_jobs()` 每次热读 jobs.json，ticker 每 60s tick，改后 60s 内生效

### 验收（2026-08-18 双重实证）

- 新建 status: mimir 测试卡 → 5 分钟内 cron agent 自动处理（追加段 + 改 status: hermes）
- cron output 从 237B（script 模板）→ 1766B（agent 完整值班报告）

---

## 旧版三步部署（已废弃，仅留档）

### 1. Gateway Daemon（18791端口）

```bash
cd MimirAether
python3 scripts/mimir-daemon.py &>/tmp/mimir-daemon-18791.log &
```

验证：
```bash
pgrep -af "mimir-daemon"
curl -s http://127.0.0.1:18791/health
```

健康端点返回 JSON（agent/status/uptime/state/area/pid）。

**陷阱：** 不要用 `python`，用 `python3`（NixOS 无 python symlink）。

### 2. Wiki Watcher Cron（每 1 分钟扫 status: mimir）

cronjob action=create:
- name: mimir-wiki-watcher
- schedule: `every 1min`
- skills: [mimiraether-cross-session, mimiraether-wiki-auto-archive]
- deliver: local
- prompt: 扫描 ~/wiki/discussions/ 下所有 .md frontmatter，找 status: mimir → 读卡分析→改 status 接力→更新 log.md/index.md

### 3. Verify Gate（每 5 分钟检测 Gateway 重启）

cronjob action=create:
- name: mimir-verify-gate
- schedule: `every 5min`
- script: verify-gate-on-wake.sh
- deliver: local
- prompt: 读 verify-gate.log 最新 20 行，有 WARN 则 grep 验证

**script 内容：** 比较当前 gateway PID 与缓存 PID，变化时 grep 最后 10 条 assistant 消息中"已完成"声明，写入 verify-gate.log。

首次运行前缓存当前 PID：
```bash
pgrep -f "gateway.run" | head -1 > ~/.mimiraether/data/.gateway-pid-cache
```

## 维护

- daemon 挂了：重新跑第一步
- cron 失效：`cronjob action=list` 查看状态
- verify-gate.log 过大：周期性 truncate
