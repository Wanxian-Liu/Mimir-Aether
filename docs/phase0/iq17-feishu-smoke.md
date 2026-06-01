# IQ-14 飞书冒烟验收（IQ #17）

> **日期**：2026-06-01 · **Owner**：刘哥（飞书会话）+ Cursor（文档对齐）  
> **状态**：**PASS**（由 **IQ-55 Phase2 飞书 3P** 证据覆盖，见下表）  
> **真源计划**：[`MIMIR_IQ17_EXECUTION_PLAN.md`](../MIMIR_IQ17_EXECUTION_PLAN.md) § IQ-14

---

## 1. IQ-14 三条与 IQ-55 映射

| IQ-14 # | IQ-14 验收句 | 覆盖证据 | 判定 |
|---------|----------------|----------|:----:|
| 1 | 还记得我们上次关于 IQ 的决定吗 | Phase2 ① `session_search`（Wave A 结论）· traj `94ab78b400af988f` | **PASS** |
| 2 | 你进步了吗 / 状态怎么样 | Phase2 ② memory + `session_search` + search-first 偏好写入 · traj `7f9b3e3b5469e892` | **PASS** |
| 3 | 继续执行 TASK_QUEUE §11 下一粒 | Phase2 ③ Gateway 单实例 · traj `16e3735611f87e85` · 引用 `ensure_single_gateway.sh` | **PASS** |

**汇总**：**3/3 PASS**（与 [`iq-55-phase2-closeout.md`](./iq-55-phase2-closeout.md) Q2、[`iqevo-30-feishu-smoke-evidence.md`](./iqevo-30-feishu-smoke-evidence.md) 一致）

---

## 2. 复验命令（只读）

```bash
# Gateway
curl -s http://127.0.0.1:18999/health | head -c 300

# ③ 轨迹（Phase2 PASS）
test -f ~/.mimiraether/data/trajectories/2026-06-01/16e3735611f87e85.jsonl && echo OK

# preemptive / search（近 7d 有即可）
rg -l 'preemptive-search|session_search' ~/.mimiraether/logs/agent.log | tail -1
```

---

## 3. 与 IQ-M 的关系

- **IQ-M1**（7d skill_view）：仍 ❌ — 与本冒烟无关，见 `iq17-closeout.md`
- **IQ-M3**：拍板已文档化 ✅
- 本文件闭合 **IQ-14** 粒；**不**宣称 rubric 已达 5.5

---

## 4. 修订

| 日期 | 摘要 |
|------|------|
| 2026-06-01 | 初版：IQ-55 3P 覆盖 IQ-14 · TASK_QUEUE §11 [x] |
