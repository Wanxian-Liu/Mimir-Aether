# IQ-17 Baseline（2026-06-01）

> 作者：Mimir · 真源：[MIMIR_IQ17_EXECUTION_PLAN.md](../MIMIR_IQ17_EXECUTION_PLAN.md)

## 1. Rubric 起点

| 维度 | 分数 |
|------|:----:|
| **I1** 跨会话回忆 | 5.0 |
| **I2** 元认知（自知力） | 4.0 |
| **I3** 学习能力（进化闭环） | 3.5 |
| **I6** 执行可靠 | 6.0 |
| **整体** | **4.9/10** |

## 2. `.env` 快照（grep `MIMIR_*` / `AUTO_EVOLVE` / `FEEDBACK`）

```bash
grep -E '^(MIMIR_|AUTO_EVOLVE|FEEDBACK)' ~/.mimiraether/.env
```

```
MIMIR_AUTO_EVOLVE=1
MIMIR_WM_VOE_LEARNING=1
MIMIR_CROSS_SESSION_RAG=1
MIMIR_FEISHU_SESSION_RETRY=1
```

无密钥泄露。

## 3. SELF-11（preemptive search）部署状态

| 文件 | 状态 |
|------|:----:|
| `agent/search_first_guard.py` | main `c5de84e` |
| `agent/prompt_builder.py` | main `c5de84e` |
| `gateway/router/agent_route_mixin.py` | main `c5de84e` |
| Gateway | 已重启（PID 144962, health OK） |
| Log 证据 | `preemptive session_search` 行已出现 |

## 4. tier0 基线

```
677 passed, 4 failed, 10 warnings
```

**4 个 pre-existing failures**（cross_session_retrieval L2/L3，非 IQ-17 引入）：

| 测试 | 症状 |
|------|------|
| `test_prefetch_uses_objective_query` | KeyError: 'query' (mock search_fn 未被调用) |
| `test_query_falls_back_to_next_session` | KeyError: 'query' |
| `test_build_with_rag_off_matches_l2_search_fn` | empty out |
| `test_build_with_rag_on_merged_injection` | empty out |

## 5. 已有功能状态

| 项目 | 状态 |
|------|:----:|
| ENG-SF-01 / SELF-11 preemptive | ✅ 已部署 |
| intent_predictor | 已存在 `agent/intent_predictor.py` |
| SELF-12 nudge 契约 | 31 项测试通过 |
| AUTO_EVOLVE code | 已合入，默认=0，.env=1 |

## 6. IQ-M2 初值（search-first 违规率）

本粒尚未跑 audit（IQ-15 执行）。SELF-13 baseline: **100%** filtered_violation_rate。
