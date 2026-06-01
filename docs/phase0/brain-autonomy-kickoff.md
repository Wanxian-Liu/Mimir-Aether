# Brain Autonomy Kickoff — BRAIN-00

> **日期**：2026-06-01  
> **SHA**：`38c21e9`  
> **状态**：§11 IQ#17 全 [x] ✅ → 开启 §10 大脑自治链

## Gateway

| 指标 | 值 |
|------|:--:|
| Health | `ok` |
| Agent error rate | **0.10** (10%) |
| Tool p50 | 1,164ms |
| Tool p95 | 87,187ms |

Agent error rate 10% 偏高（阈值 10%），工具 P95 87s 也高（可能含 timeout 重试）。进入 Wave 1 后注意监控。

## 数据库基础

| 指标 | 值 |
|------|:---:|
| sessions_search.db 总会话 | 67 |
| 总消息 | 16,613 |
| 7d 会话 | 67（DB 全量在 7d 内） |

## 环境变量状态

| 变量 | 值 | 说明 |
|------|:--:|------|
| `MIMIR_AUTO_ANALYSIS` | 1 | ✅ 已开 |
| `MIMIR_FEEDBACK_COLLECTOR` | 1 | ✅ 已开 |
| `MIMIR_AUTO_EVOLVE` | 1 | ✅ 已开 |
| `MIMIR_WM_VOE_LEARNING` | 1 | ✅ 已开 |
| `MIMIR_WM_VOE_REPLAN_CTX` | 1 | ✅ 已开（IQ-30） |

## IQ 基线

| 维度 | 分 |
|------|:--:|
| 当前 IQ | 5.2/10（距 5.5 合格线差 **0.3**） |
| 距 Q1～Q7 | 4/7 项接近达标，3 项需 Wave 1～2 |

## 下一粒

→ **BRAIN-01**（Wave 1 · 感知与闭环：Intent → 检索肌肉）
