#!/usr/bin/env python3
"""
delegation_guard.py — 反向清单过滤（Loki 12 类不该委派 · 🔴 五类永拒 · 触发前置闸）

出处（盘上证据）：
- Loki 方案-块3 四方卡 L2641-2649：🔴 永远不该委派 5 类（白名单拒绝）
  ┌ 1 单步直接操作（read_file/write_file/patch）——4.4x 错误放大 + 子代理写盘破坏可追溯
  ├ 2 高度串行依赖任务（读→析→写→验）——协调开销 -39% 抵消收益 + 上下文污染
  ├ 3 短上下文任务（<10K token）——multi-agent 用 ~15x token，通信开销 > 实际收益
  ├ 4 写盘类（write/patch）——落盘权归 orchestrator——子代理产出不可信 + 主线程失守
  └ 5 需审计留痕的关键决策（财务/合同/对外承诺）——子代理决策不可追溯 + 法律责任不清
- 段 1 最终触发公式（四方卡 L3496-3504）：
    触发 = est_turns>=8 AND parallel_elig>=2 AND 类型∈{多源/批量/扫描}
           AND 无写盘副作用 AND NOT 12 类不该委派反例
  执行顺序：反例清单（拒绝）→ AND 触发条件 → 成本闸——**反例清单必须在最前**（本闸即前置闸）

用法：
    from agent.delegation_guard import check_delegation_guard
    allow, reason = check_delegation_guard(task_spec, messages=history)
    # allow=False → 命中不该委派清单，禁止委派（reason 含类别 + 证据）
    # allow=True  → 通过前置闸（允许进入触发公式评估）

环境开关：
    MIMIR_DELEGATION_GUARD=1  默认开（启用反向清单过滤）
    MIMIR_DELEGATION_GUARD=0  回退（放行不拦截——保留触发公式原行为）
"""

import os
import re
from typing import List, Optional, Tuple

GUARD_ENV = "MIMIR_DELEGATION_GUARD"
SHORT_CONTEXT_TOKEN_THRESHOLD = 10_000  # Loki 12 类 #3：<10K token 不该委派

# ---------------------------------------------------------------------------
# 🔴 类别 5 · 需审计留痕的关键决策（财务/合同/对外承诺/凭证）
#   四方卡 L2649 | SOUL.md 第 3 条红线——子代理决策不可追溯 + 法律责任不清
# ---------------------------------------------------------------------------
_AUDIT_KEYWORDS = (
    r"(财务|合同|对外承诺|审批|签约|报价|法律责任|审计留痕|法务|合规|对赌|赔偿)"
    r"|(凭证|密钥|密码|token|password|api\s*[_-]?\s*key|secret)[\s:：]"
)

# ---------------------------------------------------------------------------
# 🔴 类别 4 · 写盘类（write/patch/commit/部署）
#   四方卡 L2648 | OpenClaw"落盘权归 orchestrator"——子代理产出不可信 + 主线程失守
# ---------------------------------------------------------------------------
_DISK_WRITE_KEYWORDS = (
    r"(write_file|writefile|patch)\b"
    r"|落盘|写盘|写入(?:文件|到)?|保存到|写到|覆盖(?:文件|原文件)?"
    r"|git\s+(commit|push)|commit\b|推送|部署|发布(?:到|至)?\s*\S*"
)

# ---------------------------------------------------------------------------
# 🔴 类别 1 · 单步直接操作（一次工具调用即可完成）
#   四方卡 L2645 | 4.4x 错误放大 + 子代理写盘破坏可追溯
# ---------------------------------------------------------------------------
_SINGLE_STEP_PATTERNS = (
    r"^read_file\s+\S+",
    r"^write_file\s+",
    r"^patch\s+",
    r"^(cat|ls|grep|rg|stat|tail|head|wc|find)\s+\S+",
    r"^(读|看|查)(一下|取)\s*\S+",             # 读一下 X / 读取 Y / 查一下 Z（限限定词——防误捕箭头链）
    r"^(打开|读取|查看|检查)\s+\S+[\./]",        # 打开文件/查看路径
)
_SINGLE_STEP_TOOL_CALL_RE = re.compile(
    r"\b(read_file|write_file|patch|search_files|terminal)\s*\("
)

# ---------------------------------------------------------------------------
# 🔴 类别 2 · 高度串行依赖任务（读→析→写→验 链条）
#   四方卡 L2646 | 协调开销 -39% 抵消收益 + 上下文污染
# ---------------------------------------------------------------------------
_SERIAL_CHAIN_PATTERNS = (
    r"读\s*→|→\s*析|析\s*→|→\s*写|写\s*→|→\s*验",      # 显式箭头链（读→析→写→验）
    r"(先|第一步|首先).*(再|然后|接着).*(再|最后).*(验|提交|落盘)",  # 分步顺序词
    r"串行|依赖链|顺序执行|链式|链条|串联",
    r"基于.{0,12}(结果|输出|上一步).*(继续|下一步)",     # 上一步输出驱动下一步
    r"step\s*by\s*step|sequential",
)

# ---------------------------------------------------------------------------
# 🔴 类别 3 · 短上下文任务（<10K token）
#   四方卡 L2647 | multi-agent 用 ~15x token——通信开销 > 实际收益
# ---------------------------------------------------------------------------
_SHORT_CONTEXT_PATTERNS = (
    r"\d+\s*(行|字|个工具调用|次调用|步)\s*(以内|内|就行|即可|就够|搞定)",
    r"一句话|几秒钟|几分钟就|很简单的?(任务|事)|随手",
)

_AUDIT_RE = re.compile(_AUDIT_KEYWORDS, re.IGNORECASE)
_DISK_WRITE_RE = re.compile(_DISK_WRITE_KEYWORDS, re.IGNORECASE)
_SERIAL_CHAIN_RES = [re.compile(p, re.IGNORECASE) for p in _SERIAL_CHAIN_PATTERNS]
_SHORT_CONTEXT_RES = [re.compile(p, re.IGNORECASE) for p in _SHORT_CONTEXT_PATTERNS]


def _estimate_tokens(messages: Optional[List]) -> int:
    """粗估消息 token（字符数/4——与 model_metadata.estimate_messages_tokens_rough 同口径）。"""
    total_chars = 0
    for m in messages or []:
        if isinstance(m, dict):
            total_chars += len(str(m.get("content", "")))
        else:
            total_chars += len(str(m))
    return max(1, total_chars // 4)


def delegation_guard_enabled() -> bool:
    """MIMIR_DELEGATION_GUARD 开关——默认 1（开）；=0 回退（放行）。"""
    return os.environ.get(GUARD_ENV, "1") != "0"


def check_delegation_guard(
    task_spec: str, messages: Optional[List] = None
) -> Tuple[bool, str]:
    """反向清单前置闸（段 1 公式第 3 变量·触发前置过滤）。

    Loki 12 类不该委派（🔴 五类永拒）——命中任一 → 禁止委派 + 理由。

    Args:
        task_spec: 任务书文本（将委派给子代理的 goal/描述）。
        messages: 可选——当前会话消息历史，用于估算上下文 token（<10K 判短上下文）。

    Returns:
        (allow, reason):
            allow=False → 命中不该委派清单——禁止委派，reason 含类别 + 证据；
            allow=True  → 通过前置闸——允许进入触发公式评估。
    """
    if not delegation_guard_enabled():
        return True, f"{GUARD_ENV}=0 回退——反向清单过滤关闭（放行）"

    spec = task_spec.strip() if task_spec else ""
    if not spec:
        return True, "task_spec 为空——无内容可判，放行（由触发公式自行判断）"

    # ── 类别 5 · 需审计留痕（最优先——红线最高）──────────────────────
    m = _AUDIT_RE.search(spec)
    if m:
        return False, (
            "类别5·需审计留痕：命中关键决策关键词「%s」——财务/合同/对外承诺/"
            "凭证类决策必须主线程亲自执行（四方卡 L2649 · 子代理决策不可追溯）"
            % m.group(0).strip()
        )

    # ── 类别 4 · 写盘类/commit 决策（落盘权归 orchestrator）──────────
    m = _DISK_WRITE_RE.search(spec)
    if m:
        return False, (
            "类别4·写盘类：命中写盘/commit 关键词「%s」——落盘权归 orchestrator，"
            "子代理产出不可信 + 主线程失守（四方卡 L2648）" % m.group(0).strip()
        )

    # ── 类别 1 · 单步直接操作 ────────────────────────────────────────
    for pat in _SINGLE_STEP_PATTERNS:
        if re.match(pat, spec, re.IGNORECASE):
            return False, (
                "类别1·单步直接：任务书是单次直接操作「%s」——4.4x 错误放大，"
                "主线程自己执行更快更可追溯（四方卡 L2645）"
                % spec[:60]
            )
    tool_calls = _SINGLE_STEP_TOOL_CALL_RE.findall(spec)
    if len(tool_calls) == 1:
        return False, (
            "类别1·单步直接：任务书仅含 1 次工具调用（%s）——单步任务不值得委派"
            "（四方卡 L2645）" % tool_calls[0]
        )

    # ── 类别 2 · 高度串行依赖 ────────────────────────────────────────
    for res in _SERIAL_CHAIN_RES:
        m = res.search(spec)
        if m:
            return False, (
                f"类别2·高度串行依赖：命中串行链信号「{m.group(0).strip()}」"
                f"——读→析→写→验 链条协调开销 -39% 抵消收益 + 上下文污染"
                f"（四方卡 L2646）"
            )

    # ── 类别 3 · 短上下文（<10K token）───────────────────────────────
    tokens = _estimate_tokens(messages) if messages else None
    if tokens is not None and tokens < SHORT_CONTEXT_TOKEN_THRESHOLD:
        return False, (
            "类别3·短上下文：当前上下文约 %d token（< %d）——multi-agent 通信开销"
            " > 实际收益（~15x token，四方卡 L2647）——主线程直接做" % (
                tokens, SHORT_CONTEXT_TOKEN_THRESHOLD
            )
        )
    for res in _SHORT_CONTEXT_RES:
        m = res.search(spec)
        if m:
            return False, (
                "类别3·短上下文：任务书自述「%s」工作量极小——不值得委派"
                "（四方卡 L2647）" % m.group(0).strip()
            )

    return True, "通过反向清单前置闸——未命中 12 类不该委派（可进入触发公式评估）"


__all__ = [
    "GUARD_ENV",
    "SHORT_CONTEXT_TOKEN_THRESHOLD",
    "check_delegation_guard",
    "delegation_guard_enabled",
]
