---
name: p0-index-health-monitor
description: P0 chroma/bge-m3 语义索引健康监控的标准作业流程（跑监控 → 复算四项 checks → 按任务书字面格式汇报）。触发词：P0 chroma 索引健康监控 / p0_index_monitor / 索引退化。
auto_load: false
---

# P0 索引健康监控 SOP

## 触发
- cron job `1bc613c4aa65`「P0 chroma 索引健康监控」每 6h 触发；或用户直接派发同一任务书。

## 1. 跑监控（一条命令，勿包装）
```
cd /home/rayliu/.mimiraether/scripts/p0 && /home/rayliu/src/MimirAether/.venv/bin/python3 p0_index_monitor.py; echo "EXIT=$?"
```
- exit 0 = 健康；exit 2 = 有异常项。
- **不要** `tee` 第二份副本：脚本自身已写 canonical 产物
  `/home/rayliu/.mimiraether/data/p0_index_health.json`（约 376 B）。多一份 = 同数据两副本（曾犯）。

## 2. 复算四项 checks（读盘 json.load，不凭输出截图）
| 项 | 判据 |
|---|---|
| 漂移 | `abs(chroma_docs - source_indexable) / source_indexable * 100 <= 2.0` |
| 垃圾 | `garbage_in_index == 0`（>0 = 垃圾回潮，需报告） |
| backfill | `backfill_phase == "done"` |
| 增量 | `incremental_enabled is True` |

退化特征（区别于安静期）：**chroma_docs 掉而 source_indexable 不降**；两者同降或同平 = 正常。

## 3. 汇报格式（硬要求：逐字复现任务书清单）
`agent/task_completion.py` 的提醒门是**逐字子串**匹配（L46 取 `- [ ]` 原文；L50-56 只看最近 3 条 assistant 消息；L56 `it not in joined`）——
**意译/改写标点 ⇒ 每轮被报「5 项未交付」**。做法：把 5 项原文各占**单行、不断行**，行尾接 `→ 证据`。
单项示例如：`[1] 用 terminal 执行上面的监控命令，拿到 JSON 输出 → ...`
（后果：只抄清单不干活也能过门；该门是措辞匹配器，非交付验证器。）

## 4. 环境真值
- 本机 **TZ=UTC+8**；`~/.mimiraether/cron/jobs.json` 的 `last_run_at/next_run_at` 记 **UTC**。
  例：`06:46:54Z` = 本机 14:46 —— 正是那次任务送达时刻，**不是**时钟错位。
- `source_garbage` 基线：任务书记 201；2026-09-22~24 实测恒 205（差 4，未增长）⇒ 记录即可，非异常。

## 5. 已知基线读数（漂移恒定 +2）
- 09-22 14:42 → 20860 / 20862
- 09-23 14:46 → 20868 / 20870
- 09-23 20:47 → 20872 / 20874
- 09-24 02:48 → 20872 / 20874
- 09-24 08:49 → 20872 / 20874
- 09-24 14:49 → 20880 / 20882（+8 增量消化，漂移仍 +2）

## 6. 出问题时
走 `mimiraether-root-cause-debugging` 四阶段：先读 `scripts/p0/p0_index_monitor.py`（4646 B，08-11 定版）+ 复现，
再决定修监控脚本还是修索引管线；**先落盘取证**（notes/）再改码。
