"""agent/injection_prefixes.py — 注入块前缀单一真源（2026-10-26 · PI 触发根因修复 D1）

背景（根因取证 · ~/wiki/discussions/2026-10-26-PI子代理未触发-根因取证-mimir.md）：
- `agent_loop` 在 turn 0 会先把 intent-context / 记忆 nudge / 技能 nudge / 空跑闸门等
  **以 role=user 追加**进 messages，然后才调 PI 触发评估 `maybe_pi_delegate_execute(messages)`。
- `pi_trigger._extract_user_task` 原跳过表只有 `("[MIMIR_", "[CONTEXT")`
  ⇒ 认不出 `<intent-context>` / `【空跑闸门】` 等注入块 ⇒
  **把 210 字符的 intent 注入块当成「用户派单」打分，est 恒 = 4**（历史实证 55/55 次）。
- 本模块 = 两份前缀表的**唯一真源**：`agent_loop._INTENT_SKIP_PREFIXES` 与
  `pi_trigger._extract_user_task` 都从这里取，禁止各自散落。

维护约束：
- 新增任何「以 role=user 注入」的块，**必须**同时在此登记前缀，否则会被当成真实用户消息
  （后果：intent 重估自触发 + PI 打分错对象 + search-first 误判）。
- 只登记「块首固定前缀」，不做正则（调用方用 startswith 判定）。
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# 英文/ASCII 前缀（含方括号与尖括号两种外壳）
# ---------------------------------------------------------------------------
INJECTION_PREFIXES_ASCII = (
    "[BLOCKED",
    "[SEARCH-FIRST",
    "[MIMIR_",              # PI nudge / parallel-read nudge / 半段 staging 等
    "[intent-action-guard]",
    "[intent-context]",
    "<intent-context>",     # 2026-10-26 新增：PI 打分错对象的直接元凶
    "[HISTORY SUMMARY]",
    "[CONTEXT",
    "[HOOK",
)

# ---------------------------------------------------------------------------
# 中文方括号前缀（A1 · 2026-10-04 Mimir 角色审计 blocker 漏项族）
# ---------------------------------------------------------------------------
INJECTION_PREFIXES_CN = (
    "【架构",
    "【空跑闸门",
    "【读闸",
    "【任务完成度提示",
    "【自动唤醒",
    "【讨论室唤醒",
    "【任务】",
    "【审计统计】",
    "【Mimir · 半段",       # 空跑闸门 staging flush 块
)

# 唯一真源（调用方一律用这一个元组做 startswith 判定）
INJECTION_PREFIXES = INJECTION_PREFIXES_ASCII + INJECTION_PREFIXES_CN

# intent 重估专用别名：历史沿用名（语义 = 上述全集）
_INTENT_SKIP_PREFIXES = INJECTION_PREFIXES

# ---------------------------------------------------------------------------
# PI 打分专用（**更窄**）：只认「系统生成」的块
# ---------------------------------------------------------------------------
# 实证（2026-10-26，本修复第一版被打回）：本仓派单模板以「【任务】」起头，
#   若把 "【任务】"/"【架构" 也纳入 PI 跳过表 ⇒ **真派单被判无任务文本** ⇒
#   `est_turns` 恒 0 ⇒ PI 变成新的「恒假闸门」（本来是量错对象，改成量不到）。
#   故 PI 侧用窄表：宁可让 intent 块偶尔混进来，也不能把真派单吞掉。
PI_TASK_SKIP_PREFIXES = tuple(
    p for p in INJECTION_PREFIXES if p not in ("【任务】", "【架构")
)


def is_injected(content: str) -> bool:
    """True = 该消息是系统注入块，不是真实用户输入（intent 重估口径 · 宽表）。"""
    if not isinstance(content, str) or not content:
        return False
    return content.lstrip().startswith(INJECTION_PREFIXES)


def is_injected_pi(content: str) -> bool:
    """True = 该消息是系统注入块（**PI 打分口径 · 窄表**）。

    与 is_injected 的唯一差别：不把 "【任务】"/"【架构" 当注入——
    真实派单常以此起头（见上方实证注释）。
    """
    if not isinstance(content, str) or not content:
        return False
    return content.lstrip().startswith(PI_TASK_SKIP_PREFIXES)


__all__ = [
    "INJECTION_PREFIXES",
    "INJECTION_PREFIXES_ASCII",
    "INJECTION_PREFIXES_CN",
    "PI_TASK_SKIP_PREFIXES",
    "_INTENT_SKIP_PREFIXES",
    "is_injected",
    "is_injected_pi",
]
