# Bridge Wave 9 — 清空冲刺结案

> **日期**：2026-05-27  
> **来源**：`MIMIR_LIU_CURSOR_BRIDGE.md` §6 / §1 会话治理 → 迁入 backlog **§18**

## 做了什么

1. **Backlog §18** — 全量迁入 Hermes/OpenSpace P0～P2 + 会话治理债；§18.2 为执行源。
2. **Bridge §6 瘦身** — 只保留摘要指针，任务表不再维护于 bridge。
3. **BRIDGE-CTX-B02** — `_build_context_usage_hint()` 写入 cross-session prompt。
4. **HERM-SDH-01** — `SubdirectoryHintTracker` 接入 `core_loop` + `exec_mixin`。
5. **HERM-TGR-01** — `agent/tool_call_cache.py` 只读工具 TTL 缓存。

## 验证

- `tests/agent/test_bridge_wave9.py`
- `tests/contract/test_horizon_bridge_wave9.py`
- `./run_ralph_tier0.sh`

## 下一粒（默认）

**HERM-CUR-02** — `skill_curator` 生命周期（stale/archived）— 见 backlog §18.2。
