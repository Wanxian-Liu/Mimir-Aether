# Mimir 自主守护进程套件

## 三步部署流程

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
