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


# ── 系统注入消息识别（2026-08-18 Hermes 修复 · Mimir 审计 P0-1 根因链第二环）──
# 根因：TD-03 L1 软提示注入文本含"落盘/write_file"字样 → _task_requires_write 误判为写盘任务
#       → verify guard 对后续所有无写盘回复硬拦（"Done!" 等收尾语被拦）→ 与 TD-03 叠加死循环。
# 修复：_last_user_text 等只认真实用户消息，跳过系统注入（guard 提示/软提示/intent-context/skill nudge）。
_SYSTEM_INJECT_PREFIXES = (
    "[MIMIR_", "[BLOCKED:", "[SEARCH-FIRST", "<intent-context>",
    "【架构产出提示】", "[intent-action-guard]",
)

def _is_system_inject(msg: dict[str, Any]) -> bool:
    """系统注入的 user 消息（guard 提示/软提示/intent 上下文）——非真实用户指令。"""
    if msg.get("role") != "user":
        return False
    c = msg.get("content")
    if not isinstance(c, str):
        return False
    return c.startswith(_SYSTEM_INJECT_PREFIXES)


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str) and not _is_system_inject(msg):
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
            if _is_system_inject(msg):
                continue  # 系统注入消息不构成边界——继续找真实 user
            break
    return False


# ── P0修复（2026-08-05，Hermes深挖根因后三思设计）──
# 缺陷：guard把"读过文件"当"验证过写盘"——write_file/patch不在验证工具集，
# 导致Mimir调查15步（全是read_file）→ guard放行 → 没写盘就结束。
# 修复：区分"调查工具"与"写盘工具"——写盘任务必须真有写盘动作才放行。

WRITE_TOOLS = {"write_file", "patch", "apply_patch", "edit"}

# ── P0-2（2026-09-28 · 空跑专题第 4 次近因 · 审计会2 交叉审计）──────────────
# 病灶（**闸门互斥**）：本闸原先只认 WRITE_TOOLS（write_file/patch/…）⇒
#   `execute_code` 写交付卡的 run 被本闸判「没写」⇒ 干完活了还被拦 + 回复被移出历史；
#   而**空跑闸**（agent/empty_run_gate）同期判「写了」⇒ 两闸对同一事实相反判据 = 互斥。
# 修法：写动作判定**不在本文件重复实现** —— 单一真源 = `empty_run_gate.classify_tool()`，
#   它对 execute_code/terminal 走**内容级**判据（真写才 write，纯读仍 readonly）。
#   ⚠️ 本文件不得再自建一份「写/只读」判据（第 5 份副本 = 下一次互斥）。
WRITE_CAPABLE_EXEC_TOOLS = frozenset({"execute_code", "terminal"})


def _shared_classifier():
    """写动作分类器：单一真源（empty_run_gate）。导入失败 ⇒ 回退旧口径（不比现状更差）。"""
    _m = None
    try:
        from . import empty_run_gate as _m  # type: ignore
    except Exception:
        try:
            import empty_run_gate as _m  # type: ignore
        except Exception:
            _m = None
    if _m is not None and hasattr(_m, "classify_tool"):
        return _m.classify_tool, getattr(_m, "_tc_args", None)

    def _fallback(name: str, args_raw: str = "") -> str:
        return "write" if name in WRITE_TOOLS else "readonly"

    return _fallback, None

WRITE_TASK_MARKERS = ["写", "写入", "落盘", "追加", "完成你的段", "输出到", "创建", "更新文件", "写到"]


# ── E5-A1（2026-09-27）：否定语境短路 ──
# 病灶（决定性证据）：委派 E2E 原文「…把原文返回给我（**不要落盘**、不要修改任何文件）」是纯只读任务，
#   而 `any(m in last_user …)` 命中的标记正是 **`落盘`** —— 它出现在否定短语「不要落盘」里。
#   ⇒ 越强调「不要落盘」，越被判为「写盘任务」⇒ 只读任务永远拿不出 write_file ⇒ verify 3/3 耗尽
#   ⇒ 正确答案被故障文案顶掉（子代理黑洞 + 当日 26 次硬拦同源）。
# 修法：标记词若处于否定语境（前 3 字窗口含否定字/否定词）⇒ 该次出现不计。
#   回滚：MIMIR_WRITE_TASK_NEGATION=0。
_NEGATION_CHARS = "不别勿免莫休"
_NEGATION_WORDS = ("无需", "不用", "禁止", "不能", "不必", "无须")
_NEGATION_WINDOW = 3


def _marker_is_negated(text: str, idx: int) -> bool:
    """标记词是否处于否定语境（只看前 _NEGATION_WINDOW 字，覆盖「不要落盘」「别写入」「无需创建」「禁止写」）。"""
    window = text[max(0, idx - _NEGATION_WINDOW):idx]
    if any(ch in window for ch in _NEGATION_CHARS):
        return True
    return any(w in window for w in _NEGATION_WORDS)


def _task_requires_write(messages: list[dict[str, Any]]) -> bool:
    """判断任务是否要求写盘（从最近user消息检测）。

    E5-A1：任一标记词处于否定语境时不计（防「不要落盘」被读成写盘任务）。
    """
    last_user = _last_user_text(messages)
    if not last_user:
        return False
    _neg_on = os.environ.get("MIMIR_WRITE_TASK_NEGATION", "1").strip().lower() not in ("0", "false", "no")
    for _mk in WRITE_TASK_MARKERS:
        _start = 0
        while True:
            _idx = last_user.find(_mk, _start)
            if _idx < 0:
                break
            if not (_neg_on and _marker_is_negated(last_user, _idx)):
                return True
            _start = _idx + 1
    return False


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
    """检查本轮（最近真实 user 之后）是否有任何工具调用。"""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            return True
        if msg.get("role") == "user":
            if _is_system_inject(msg):
                continue
            break
    return False


def _has_written_this_turn(messages: list[dict[str, Any]]) -> bool:
    """检查本轮是否有写盘动作。

    P0-2（2026-09-28）：判据改**单一真源** = `empty_run_gate.classify_tool`（内容级）——
    `execute_code`/`terminal` 真写了文件才算 write（纯读不算）；与空跑闸同口径，
    治「两闸对同一事实相反判据」（execute_code 写交付卡 ⇒ 本闸误判没写 ⇒ 硬拦）。
    """
    classify, tc_args = _shared_classifier()
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                try:
                    name = (tc.get("function", {}) or {}).get("name", "") or ""
                except AttributeError:
                    continue
                raw = ""
                if tc_args is not None:
                    try:
                        raw = tc_args(tc) or ""
                    except Exception:
                        raw = ""
                try:
                    if classify(name, raw) == "write":
                        return True
                except Exception:  # 量具异常不得影响判定（fail-open：被观测对象优先）
                    if name in WRITE_TOOLS:
                        return True
        if msg.get("role") == "user":
            if _is_system_inject(msg):
                continue
            break
    return False


_LAST_BLOCK_REASON: str | None = None


def _set_block_reason(reason: str | None) -> None:
    """RS17：记录本次拦截原因，供 build_nudge_message 分派对应提示。"""
    global _LAST_BLOCK_REASON
    _LAST_BLOCK_REASON = reason


def get_last_block_reason() -> str | None:
    return _LAST_BLOCK_REASON


def should_block_finish(messages: list[dict[str, Any]], assistant_text: str) -> bool:
    if not guard_enabled():
        return False
    _set_block_reason(None)  # RS17：每次判定先清空上一次原因
    # 自引用豁免：讨论守卫本身时跳过（含中文/英文关键词）
    text_lower = (assistant_text or "").lower()
    if any(kw in text_lower for kw in ["verify-before-report", "守卫", "before-report", "before_report"]):
        return False
    last_user = _last_user_text(messages)
    if last_user and any(p in last_user for p in STATUS_QUERY_PATTERNS):
        return False

    # R2（2026-09-21）：判定起点标记 —— 供 evaluate_finish() 判断「本轮真的判过」。
    # 位置 = 通过全部豁免（守卫关闭 / 自引用 / 状态查询）之后 ⇒ 未判定的回合不记账。
    _mark_judged()

    # ── RS17（2026-09-14 刘哥批准）：探针自证闸 ──
    # 缺陷：下面 _has_verified_this_turn 把"调过任意工具"当"验证过"——探针本身失效
    #       （未转义正则 / 词典序比时刻）照样放行 ⇒ 09-12 命名后两天重犯 14 次。
    # 修复：声明类结论（未生效/为 0/缺失/从未…）须附"控制组通过的探针自证"；
    #       缺自证 ⇒ 拦截，并把该声明自动记为 UNVERIFIED（不许当事实用）。
    try:
        from . import probe_attest as _probe_attest
    except ImportError:  # pragma: no cover - 以脚本方式导入时
        import probe_attest as _probe_attest  # type: ignore
    _probe_verdict = _probe_attest.evaluate_turn(assistant_text, messages=messages)
    if _probe_verdict and _probe_verdict.get("blocked"):
        _set_block_reason("probe_attest")
        return True

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
    # RS17：探针自证拦截 → 给可执行的自证指引（而不是笼统的"先验证"）
    if _LAST_BLOCK_REASON == "probe_attest":
        try:
            from . import probe_attest as _probe_attest
        except ImportError:  # pragma: no cover
            import probe_attest as _probe_attest  # type: ignore
        return _probe_attest.build_nudge()
    return (
        "[BLOCKED:verify-before-report] 你的回复被阻止——含有未经验证的声明性结论。"
        "你的回复已被从历史记录中移除。请先调用 read_file / json.load / terminal 等工具"
        "确认盘上证据真实存在，再重新输出结论。不要凭记忆报告。"
    )


# ===========================================================================
# R2（2026-09-21）：量具生产端接线 —— 判定 + 记账
# ---------------------------------------------------------------------------
# 背景：`data/verification_results.jsonl` **从未被创建**（0 写端），而读端
# `if not log_path.exists(): return {"total": 0}` ⇒「无数据」被伪装成「无失败」。
# 本段是**纯加法**：`should_block_finish()` 逐字未改（返回值由测试钉住逐位相同）；
# 记账走 `evaluate_finish()`（agent_loop 的 verify 分支已改用它）。
# 量具任何异常都不得影响判定（fail-open：被观测对象优先）。
# ===========================================================================
import logging as _logging  # noqa: E402  （追加段自带 import，不改动既有 import 块）

_ledger_logger = _logging.getLogger(__name__)

_LAST_JUDGED: bool = False


def _mark_judged() -> None:
    """标记「本轮守卫真的进入了判定」（由 should_block_finish 在豁免之后调用）。"""
    global _LAST_JUDGED
    _LAST_JUDGED = True


def _last_tool_name(messages: list[dict[str, Any]]) -> str:
    """本轮（最近一个真实 user 之后）最后一个工具名 —— 供量具 `tool` 字段。"""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in reversed(msg["tool_calls"]):
                name = tc.get("function", {}).get("name", "")
                if name:
                    return name
            continue
        if msg.get("role") == "user":
            if _is_system_inject(msg):
                continue
            break
    return ""


def _turn_has_claim(assistant_text: str, block_reason: "str | None") -> bool:
    """本轮是否出现「需判定的声明」—— 只有出现声明的判定才记账（防刷量）。

    判据与守卫自身的判定面一致：RS17 探针闸判过 / TD-04 空洞确认模板 / 命中 VERIFY_TRIGGERS。
    """
    if block_reason == "probe_attest":
        return True
    if _is_hollow_ack(assistant_text):
        return True
    text = (assistant_text or "").lower()
    return any(trigger.lower() in text for trigger in VERIFY_TRIGGERS)


def _failure_type_for(messages: list[dict[str, Any]], assistant_text: str,
                      block_reason: "str | None") -> str:
    """拦截原因 → 量具 failure_type（与读端 by_type 统计口径对齐）。"""
    if block_reason == "probe_attest":
        return "probe_attest_unverified"
    if _is_hollow_ack(assistant_text):
        return "hollow_ack_no_action"
    if _task_requires_write(messages):
        return "write_claim_without_write_action"
    return "claim_without_verification"


def evaluate_finish(messages: list[dict[str, Any]], assistant_text: str) -> bool:
    """verify-before-report 守卫的**生产端入口**（R2）：判定 + 记账。

    · 返回值与 `should_block_finish()` **逐位相同**（纯加法，测试钉住）；
    · 记账条件 =「真的判过」且「本轮出现声明」；passed = 未被拦截；
    · 落点 `<mimir home>/data/verification_results.jsonl`（读口 `agent.verification_ledger`）。
    """
    global _LAST_JUDGED
    _LAST_JUDGED = False
    blocked = should_block_finish(messages, assistant_text)
    try:
        if _LAST_JUDGED and _turn_has_claim(assistant_text, get_last_block_reason()):
            from .verification_ledger import record_verification_result as _record

            _record(
                passed=not blocked,
                failure_type=(_failure_type_for(messages, assistant_text,
                                                get_last_block_reason())
                              if blocked else None),
                tool=_last_tool_name(messages),
                message=assistant_text or "",
                claim=assistant_text or "",
                user=_last_user_text(messages),
                source="verify_before_report_guard",
            )
    except Exception as exc:  # pragma: no cover - fail-open：量具不得阻断守卫
        _ledger_logger.debug("[verify-guard] ledger record skipped: %s", exc)
    return blocked
