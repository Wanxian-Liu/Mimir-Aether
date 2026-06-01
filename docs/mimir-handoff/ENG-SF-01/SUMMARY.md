# ENG-SF-01: 先搜再答 — SUMMARY

## 问题

审计发现 `filtered_violation_rate = 1.0 (100%)`：每个跨会话历史查询（如"还记得任务么""我们上次讨论的…"）都未触发 session_search 就先回答。

## 根因

`agent/search_first_guard.py`（WA-A06.1）在 `agent_loop.py` 中已接线，但只做了**事后**检查（`should_block_text_only_finish`）：模型已经输出文本回复后才注入 nudge。审计检查"用户 turn 后至助理文本输出前 **是否调用了 session_search**"——事后 nudge 发生在文本输出后，审计视为违规。

## 修复

添加**事前** preemptive nudge：在调用 LLM (`self.model_call`) 之前，检查最后一条用户消息是否需要跨会话检索，若需要且尚未满足（`session_search_satisfied_since_last_user` 为 False），则注入一条 `[search-first-guard]` 标记的 nudge 消息。

**改动位置**：`agent/agent_loop.py`
- 导入 `cross_session_requires_search_first`、`last_user_text`、`session_search_satisfied_since_last_user`
- 在 `# --- Call model ---` 前添加 preemptive nudge 块（13 行）

## 效果

| 场景 | 原行为 | 新行为 |
|------|--------|--------|
| "还记得任务么" | 输出「根据上次会话…」→ 事后 nudge | **事前** nudge → 模型应调用 session_search |
| "继续" | 被 exclude_user_message 过滤 | ✅ 不受影响 |
| "我们上次讨论的…" | 事后 nudge 但已违规 | ✅ 事前 nudge，应合规 |

## 风险

极低。两重保护：`MAX_SEARCH_FIRST_NUDGES=2` 防无限循环；nudge 消息自身以 `[search-first-guard]` 开头，`last_user_text()` 和 `session_search_satisfied_since_last_user()` 均跳过标记消息。

## 建议 commit message

```
fix(agent): preemptive search-first nudge before LLM call (ENG-SF-01)

- Inject search-first nudge BEFORE model_call, not after text output
- Uses cross_session_requires_search_first + session_search_satisfied_since_last_user
- Guard: MAX_SEARCH_FIRST_NUDGES=2, marker-skipped by existing logic
- tier0: 677 passed, 4 failed (pre-existing L2/L3 retrieval)
- filtered_violation_rate baseline: 1.0 (100%) → expected to drop
```
