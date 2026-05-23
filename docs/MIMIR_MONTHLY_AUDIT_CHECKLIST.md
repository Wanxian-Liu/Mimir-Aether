# MimirAether 月度审计清单

> **用途**：每月运行一次，逐条勾选，避免遗漏导致问题积累 2 周+  
> **对标**：EV-M d-N 审计流程（d1–d7）规范化  
> **基线**：tier0 181+2 PASS · TRUNCATE=19  
> **最近运行**：2026-05-21（首次）

---

## A. Gateway 运行态（4 条）

| # | 检查项 | 命令/方法 | 预期 | 本次 |
|---|--------|----------|------|:--:|
| A1 | Gateway 进程存活 | `pgrep -f "gateway/run.py"` | PID 存在且常驻 >5min | |
| A2 | 软重启不丢 PID | `pgrep` → 发 SIGHUP → `pgrep` | PID 不变 | |
| A3 | 飞书 WebSocket 连通 | `grep "lark.*ws" gateway.log \| tail -3` | 无 closed / 无 connection refused | |
| A4 | Cron ticker 心跳 | `grep "Cron ticker" gateway.log \| tail -3` | ≤5min 间隔，无断档 | |

## B. Agent 健康（4 条）

| # | 检查项 | 命令/方法 | 预期 | 本次 |
|---|--------|----------|------|:--:|
| B1 | TRUNCATE 计数 | `grep -c 'Level 3 TRUNCATE' agent.log` | ≤19（基线 2026-05-20）；若涨 >2 → P0 | |
| B2 | Agent 错误分类 | `grep -E "(NameError|ImportError|AttributeError|ModuleNotFoundError)" agent.log \| wc -l` | 0 新增（IR-20260520 护栏） | |
| B3 | DeepSeek tool call 格式 | `grep -c 'tool must be a response' agent.log` | 0 | |
| B4 | 上下文溢出误伤 | 对照 B1 和 B2 — TRUNCATE 上涨但无代码错误 | 无"误截断"（B1↑ 必须 B2=0） | |

## C. 数据完整性（4 条）

| # | 检查项 | 命令/方法 | 预期 | 本次 |
|---|--------|----------|------|:--:|
| C1 | persistent.json 大小 | `wc -c < data/persistent.json` | ≥500 bytes（Session 72 截断事故：≤200 bytes = 🔴） | |
| C2 | persistent.json 语法 | `python -c "import json; json.load(open('data/persistent.json'))"` | 无异常 | |
| C3 | 会话计数连续性 | 对比上次审计的 session_count | 有增长，无回退 | |
| C4 | 胶囊仓库计数 | `ls data/capsules/*.html 2>/dev/null \| wc -l` | 不减少 | |

## D. 技能与进化（3 条）

| # | 检查项 | 命令/方法 | 预期 | 本次 |
|---|--------|----------|------|:--:|
| D1 | 技能新鲜度 | 技能策展器 stale/dormant 计数 | stale=0, dormant=0 | |
| D2 | 技能目录 vs 策展器 | `ls -d skills/mimiraether/*/ \| wc -l` vs 策展器计数 | 差 ≤2 | |
| D3 | evolution_log 伪进化 | `grep 'simulated.*true' docs/evolution_log.md` | 0 新增行 | |

## E. 审计追踪（2 条）

| # | 检查项 | 命令/方法 | 预期 | 本次 |
|---|--------|----------|------|:--:|
| E1 | ISSUES 老化 | 扫 `MIMIR_ISSUES.md` 全部 Open 项 | 每条有 ≤30d 活动，否则标记 stale | |
| E2 | Bridge backlog 同步 | `grep '\[ \]' MIMIR_EXEC_BACKLOG.md \| wc -l` | 不过期项无新增（除非有计划内的新任务） | |

## F. tier0 门禁（1 条）

| # | 检查项 | 命令/方法 | 预期 | 本次 |
|---|--------|----------|------|:--:|
| F1 | tier0 全量 | `cd ~/src/MimirAether && ./run_ralph_tier0.sh` | 181+2 PASS（Gate1/Gate2/Gate3 全绿） | |

---

## 红警触发条件

| 条件 | 响应 |
|------|------|
| TRUNCATE 涨 >2 | 停手 → 开 ISSUES → @Cursor |
| persistent.json 截断（<200 bytes） | 从 `data/backups/` 恢复 → ISSUES |
| B2 非零 | 立即 `grep -E` 提取 → ISSUES |
| tier0 失败 | 记 ISSUES + 止步（不做任何其他改动） |

---

## 历史记录

| 日期 | 通过项 | 红警 | 备注 |
|------|:------:|:----:|------|
| 2026-05-21 | — | — | 首次建立，待首次运行 |
