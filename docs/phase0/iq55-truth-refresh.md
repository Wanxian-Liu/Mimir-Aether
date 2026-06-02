# IQ-55 诊断勘误（2026-06-02 · 可查码源）

> Mimir 诚实自检 **问题清单仍成立**；下列 **「未合入 / 不存在」** 项已过时，避免重复实现或虚报进度。

## 已合入 / 已有（勿再当 backlog 实现）

| 自检声称 | 实际（`main` @ `a0dc323`+） | 证据 |
|----------|---------------------------|------|
| intent_predictor 未合入 | **已合** | `agent/intent_predictor.py` · `agent_loop.py` turn0 |
| WM 预测器未接线 | **已接线**，默认 **关** | `wm_predict` in `agent_loop.py` · 需 `MIMIR_WM_PREDICTOR=1` |
| IQ-31 handoff 等 Cursor | **已合** | `git merge-base --is-ancestor a0dc323 HEAD` |
| IQ-40/41 仅设计稿 | **MW-04/02 已落地** | `MIMIR_NUDGE_INTERVAL` · `parallel_dispatcher.py` |
| search_first_guard 死代码 | **已接** | `agent/search_first_guard.py` + `agent_loop` finish 路径 |
| FabricationGuard 无消费方 | **契约测 + ENG-WF** | `tests/agent/test_eng_wf_fabrication_guard.py` |
| `MIMIR_AUTO_ANALYSIS` 无 | **刘哥 `.env` 已有** | `MIMIR_AUTO_ANALYSIS=1`（需验证日志/产物） |
| brain_metrics 完全不持久化 | **部分持久化** | `$MIMIR_AETHER_HOME/data/ops/brain-metrics-latest.json`（`scripts/brain_metrics_snapshot.py`） |

## 仍成立（IQ-55 真 P0/P1）

| ID | 现状（2026-06-02 复测） | 目标 |
|----|-------------------------|------|
| **P0.1** | search_first **filtered 80%**（9/10 样本窗；历史 audit 曾 95%） | ≤ **40%** |
| **P0.2** | `evolution_ledger.json` **4 条** `reason: outcome=planned` | ≥1 条 **`outcome=applied`** / 可审计 patch |
| **P0.3** | 工具 P95 **91s**（health R3） | 画像 + P95 **<10s**（7.5 级） |
| **P1.1** | intent **代码有、生产证据弱** | 7d `<intent-context>` 命中可统计 |
| **P1.2** | WM **env 未开**（刘哥批后改） | `wm_prediction needs=` 日志 |
| **P1.3** | brain_metrics **非每会话自动** | cron/SELF-LOOP 周快照 + 趋势文件 |
| **P1.4** | AUTO_ANALYSIS **开但闭环未验** | 周检 `data/ops/` 产物 |

## tier0 / IQ 分

- `iq17-closeout.md` 写 **677+4**、handoff 未合 → **文档滞后**；以 fresh `./run_ralph_tier0.sh` 为准（约 **696+2**）。
- IQ **5.2** 可保留；**5.5** 须 **P0.1+P0.2+P1.1 生产证据**，不是再合一份 handoff。

## 永久不做

- **WM-B5** LLM 预测器 — [`wm-b5-llm-predictor-deferred.md`](./wm-b5-llm-predictor-deferred.md)
