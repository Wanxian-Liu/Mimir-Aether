"""verify-before-report guard — 汇报前验证守卫。

在 assistant 回复含有声明性结论时，强制触发验证提醒。
env 门控: MIMIR_VERIFY_BEFORE_REPORT=1
TD-04（2026-08-18）：空洞确认模板硬拦截——"收到——落盘"式无工具承诺回复直接 block。
"""

import os
import json
import re
from typing import Any

VERIFY_TRIGGERS = [
    "已验证", "已完成", "已修复", "已通过", "全绿",
    "verified", "completed", "fixed", "passed",
    "PASS", "zero errors", "no failures", "all green",
    "已修", "已推送",
    "收官", "已解决", "完工", "收工", "搞定了",
]

STATUS_QUERY_PATTERNS = [
    "状态", "status", "check", "在吗", "在么",
]


def guard_enabled() -> bool:
    # 修复（2026-08-05，OpenClaw发现）：默认改为1（与scripts版一致）——原默认0导致guard形同虚设
    return os.environ.get("MIMIR_VERIFY_BEFORE_REPORT", "1") == "1"


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            return msg["content"]
    return ""


def _has_verified_this_turn(messages: list[dict[str, Any]]) -> bool:
    """检查本轮是否有调过验证工具"""
    VERIFICATION_TOOLS = {"read_file", "search_files", "terminal", "git", "memory", "mimir_ops", "get_env", "session_search"}
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                if tc.get("function", {}).get("name", "") in VERIFICATION_TOOLS:
                    return True
        if msg.get("role") == "user":
            break
    return False


# ── P0修复（2026-08-05，Hermes深挖根因后三思设计）──
# 缺陷：guard把"读过文件"当"验证过写盘"——write_file/patch不在验证工具集，
# 导致Mimir调查15步（全是read_file）→ guard放行 → 没写盘就结束。
# 修复：区分"调查工具"与"写盘工具"——写盘任务必须真有写盘动作才放行。

WRITE_TOOLS = {"write_file", "patch", "apply_patch", "edit"}

WRITE_TASK_MARKERS = ["写", "写入", "落盘", "追加", "完成你的段", "输出到", "创建", "更新文件", "写到"]


def _task_requires_write(messages: list[dict[str, Any]]) -> bool:
    """判断任务是否要求写盘（从最近user消息检测）"""
    last_user = _last_user_text(messages)
    if not last_user:
        return False
    return any(m in last_user for m in WRITE_TASK_MARKERS)


# ── TD-04（2026-08-18）：空洞确认模板硬拦截 ──
# 8/17 论文任务失败根因：Mimir 连续输出"收到——落盘"式空洞确认（无工具调用、无实质内容），
# 不触发 VERIFY_TRIGGERS（无"已完成/已验证"等声明词）→ guard 放行 → 产出校验被绕过。
# 修复：检测"收到/好的 + 承诺词 + 无工具调用 + 短回复"组合 → 直接 block。
HOLLOW_ACK_PREFIX = re.compile(r"^(收到|好的|好|ok|OK|可以)[，,。\s]*(?:——|-|—|:)*")
HOLLOW_ACK_PROMISE_WORDS = ("落盘", "写盘", "记录", "探索", "补上", "入库", "固化", "沉淀")
_HOLLOW_ACK_MAX_LEN = 80


def _is_hollow_ack(assistant_text: str | None) -> bool:
    """空洞确认模板检测：收到/好的开头 + 承诺词 + 短回复（无工具调用由调用方判定）。"""
    t = (assistant_text or "").strip()
    if not t or len(t) >= _HOLLOW_ACK_MAX_LEN:
        return False
    if not HOLLOW_ACK_PREFIX.match(t):
        return False
    return any(w in t for w in HOLLOW_ACK_PROMISE_WORDS)


def _has_any_tool_call_this_turn(messages: list[dict[str, Any]]) -> bool:
    """检查本轮（最近 user 之后）是否有任何工具调用。"""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            return True
        if msg.get("role") == "user":
            break
    return False


def _has_written_this_turn(messages: list[dict[str, Any]]) -> bool:
    """检查本轮是否有写盘动作（write_file/patch等）"""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                if tc.get("function", {}).get("name", "") in WRITE_TOOLS:
                    return True
        if msg.get("role") == "user":
            break
    return False


def should_block_finish(messages: list[dict[str, Any]], assistant_text: str) -> bool:
    if not guard_enabled():
        return False
    # 自引用豁免：讨论守卫本身时跳过（含中文/英文关键词）
    text_lower = (assistant_text or "").lower()
    if any(kw in text_lower for kw in ["verify-before-report", "守卫", "before-report", "before_report"]):
        return False
    last_user = _last_user_text(messages)
    if last_user and any(p in last_user for p in STATUS_QUERY_PATTERNS):
        return False

    # ── P0修复核心：写盘任务必须有"写盘动作"才放行 ──
    if _task_requires_write(messages):
        # 写盘任务：仅调查（read_file等）不放行——必须真有写盘工具调用
        return not _has_written_this_turn(messages)

    # 非写盘任务：保持原逻辑（调过验证工具即放行）
    if _has_verified_this_turn(messages):
        return False
    # ── TD-04（2026-08-18）：空洞确认模板硬拦截 ──
    # "收到——落盘"式承诺回复（无工具调用、无验证）→ 直接 block，LLM 无法绕过
    if _is_hollow_ack(assistant_text) and not _has_any_tool_call_this_turn(messages):
        return True
    text = (assistant_text or "").lower()
    return any(trigger.lower() in text for trigger in VERIFY_TRIGGERS)


def build_nudge_message() -> str:
    return (
        "[BLOCKED:verify-before-report] 你的回复被阻止——含有未经验证的声明性结论。"
        "你的回复已被从历史记录中移除。请先调用 read_file / json.load / terminal 等工具"
        "确认盘上证据真实存在，再重新输出结论。不要凭记忆报告。"
    )
