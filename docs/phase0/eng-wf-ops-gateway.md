# ENG-WF-01 · Gateway 单 Owner（systemd 止血）

> **日期**：2026-06-02 · **执行**：刘哥（shell）+ Cursor（证据归档）  
> **状态**：**PASS**

---

## 1. 现象

- `systemctl --user status mimiraether.service` 曾显示 **`activating (auto-restart)`**，`restart counter` 达 **2400+**
- 每 ~10s 一次：`Main process exited, status=1/FAILURE`
- 根因：单元 `ExecStart=/usr/bin/python3 gateway/run.py` 与手工 **`.venv`** Gateway（PID 占 **18999**）冲突 →「Another gateway instance is already running」

---

## 2. 处置

```bash
systemctl --user stop mimiraether.service
systemctl --user disable mimiraether.service
```

**推荐唯一启动方式**（生产手工轨）：

```bash
cd ~/src/MimirAether
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/ensure_single_gateway.sh
```

---

## 3. 验收（2026-06-02）

| 检查 | 命令 | 结果 |
|------|------|:----:|
| systemd 已停 | `systemctl --user is-active mimiraether.service` | **inactive** |
| 已禁用自启 | `systemctl --user is-enabled mimiraether.service` | **disabled** |
| 单进程 | `pgrep -af gateway/run.py` | **1** 条 · PID **183505** · `.venv/bin/python` |
| 单监听 | `ss -tlnp \| grep 18999` | **127.0.0.1:18999** → pid **183505** |
| 健康 | `curl -s http://127.0.0.1:18999/health` | **ok** · `agent_error_rate=0.0` |

**journal 末行**：`Stopped mimiraether.service`（2026-06-02 00:59:23），此后无新 restart job。

---

## 4. 修订

| 日期 | 摘要 |
|------|------|
| 2026-06-02 | stop+disable · 验收 PASS · TASK_QUEUE §12 ENG-WF-01 [x] |
