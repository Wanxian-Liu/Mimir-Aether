# P2-LONG-IQEVO · Wave 6 closeout（合格智能体）

**Date:** 2026-05-26  
**Rubric:** **4.8/10** — **documented exception**（距 **5.5** 差 **0.7**）  
**Prior:** Wave 5 **4.7/10** · IQ-EVO-26  
**tier0:** **454+2** PASS（`run_ralph_tier0.sh` 2026-05-26）

## Summary

| # | Item | Result |
|---|------|--------|
| 28 | 方向 §1.1 **4.7** + §1.5 合格表 | [x] |
| 29 | session_search 7d baseline | [x] · JSON `data/ops/session_search_baseline_7d.json` |
| 30 | 飞书 3 场景 | [x] **documented** — 7d 窗内无匹配 user 句（见 `iqevo-30-feishu-smoke-evidence.md`） |
| 31 | search-first 审计 | [x] · `iqevo-31-search-first-audit.md` |
| 32 | 离线 intent MVP | [x] · `scripts/label_intent_offline.py` |
| 33 | nudge 7d | [x] · `iqevo-33-nudge-7d.md` |
| 34 | JEPA no_candidates | [x] · `iqevo-34-jepa-candidate-rate.md` |
| 35 | artifact → prompt 只读 | [x] · `build_analysis_artifact_guidance` |
| 36 | tool_quality 周常 | [x] · `docs/ops/tool-quality-weekly.md` |
| 37 | evolution_eval 周常 | [x] · exit 0 · `memory-retrieval-compare-20260526T122238Z.json` |
| 38 | rubric #5 | **4.8/10** exception |
| 39 | ADR-002 spike | [x] · `adr-002-write-spike.md` |

## Rubric #5 deltas (4.7 → 4.8)

| # | Dim | Was | Now | Why |
|---|-----|-----|-----|-----|
| 5 | Prompt 优化 | 5.0 | **5.5** | analysis artifact 只读注入（IQ-EVO-35） |
| 8 | 意图理解 | 3.0 | **3.5** | 离线 intent 标签 MVP（非生产 Predictor） |

**未变：** #1 学习能力 **2.0**（AUTO_EVOLVE 仍关）。

## Behavior evidence (§3.2)

- **session_search:** baseline + audit scripts; 生产 7d 无跨会话关键词样本 → documented  
- **evolution_eval:** exit 0，compare JSON 路径见上  
- **tool_quality:** top5 ok% — `list_capsules/process/web_search/…` @ 1.0（见 bridge §4）

## ISSUES #12

**Resolved with documented exception** — 方向已落 backlog §15 Wave 6 全 **[x]**；智商 **4.8 < 5.5** 续 Horizon（学习/意图仍为主瓶颈）。

## Next

- 刘哥飞书补 3 场景真实对话 → 可刷新 IQ-EVO-30 为 hard pass  
- Wave 7 / Unified Plan：**禁止**默认 `AUTO_EVOLVE` 除非 bridge 授权
