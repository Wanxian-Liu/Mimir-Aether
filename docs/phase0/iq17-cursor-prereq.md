# IQ-17 Cursor PREREQ 登记

## 状态：已合入 main ✅（无需等待 Cursor）

刘哥 **2026-06-01** 已将以下修复提交到 `main`（commit `c5de84e`），Gateway 已重启，生产已生效。

| # | 文件 | 改动内容 | 验证 |
|---|------|----------|------|
| 1 | `agent/search_first_guard.py` | preemptive 视为已检索；`last_user_text` 跳过注入 nudge | `pytest tests/agent/test_nudge_contract.py` → 31 passed |
| 2 | `agent/prompt_builder.py` | 写入 `SESSION_AUTONOMY_GUIDANCE` 飞书 turn 禁止 `ensure_single_gateway` | `rg 'ensure_single_gateway' agent/prompt_builder.py` |
| 3 | `gateway/router/agent_route_mixin.py` | `reset_reason=suspended` 时不附 `◆ Model:` 块 | `rg 'reset_reason' gateway/router/agent_route_mixin.py` |
| 4 | `docs/MIMIR_SELF_IMPROVEMENT_CHAIN.md` | 飞书 turn 禁止 ensure_single_gateway 文档 | 已同步 |

## 不需要 Cursor 做

PREREQ 已合入、Gateway 已重启、tier0 681 PASS。本文件仅登记痕迹，Cursor 无需再处理。
