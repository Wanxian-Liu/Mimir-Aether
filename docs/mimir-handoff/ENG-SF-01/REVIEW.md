# ENG-SF-01: REVIEW.md

## 请 Cursor 重点看

1. **Preemptive nudge 注入点**（`agent/agent_loop.py:213-228`）：在 `# --- Call model ---` 之前，注入时机正确。使用了与事后 guard 相同的 nudge 计数器 (`search_first_nudges`) 和 `MAX_SEARCH_FIRST_NUDGES=2` 上限。nudge 消息以 `[search-first-guard]` 开头，`last_user_text()` 和 `session_search_satisfied_since_last_user()` 都会跳过此类消息，不会导致死循环。

2. **审计脚本修复**（`scripts/search_first_audit.py:77`）：内层 while 循环添加了 `_SEARCH_FIRST_MARKER` 跳过条件。如果不加，preemptive nudge（role="user"）会中断审计的搜索检测，导致所有启用 nudge 的会话被误判为违规。

3. **两层防护并存**：
   - **事前**（新加）：模型看到用户消息 + nudge → 应主动调 session_search
   - **事后**（原有）：模型仍输出文本 → text-only finish guard 注入 nudge 并重试
   - 两套共享同一计数器，互不叠加超出限制

## 已知未做

1. **无法自动回测**：因审计需要生产 session JSONL（含 preemptive nudge 记录的日志），且需要重启 Gateway 后才能产生。代码级验证通过 tier0（677 passed）。
2. **未改 `MIMIR_SEARCH_FIRST_GUARD` 默认值**：默认 `1`（开启），不需要改 `.env`。
3. **未改 SESSION_SEARCH_BACKEND**：任务明确禁止。

## 预检清单

- [x] tier0 运行（677 passed, 4 failed pre-existing）
- [x] guard 测试（3/3 passed）
- [x] 审计测试（3/3 passed）
- [x] 未改 `.env` / `data/persistent.json`
- [x] 未 git push
- [x] handoff 4 文件完整

## 飞书复验建议

Cursor 合 main 并重启 Gateway 后，建议刘哥在飞书发：
> "还记得上个对话框的任务么"
 
观察：应触发 `session_search` 调用（log 中出现 `preemptive search-first nudge` 和 `session_search` tool call），而不是直接回答。
