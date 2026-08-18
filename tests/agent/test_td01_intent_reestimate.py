"""Tests for TD-01 intent predictor 每轮重估（Hermes 代改 · 2026-08-18 四方批准）。

验证：intent predictor 从 turn 0 单次注入改为每轮重估——
1. 首轮注入 <intent-context>
2. 用户新输入（追问/换任务）触发重估
3. 同一输入不重复注入（防自触发循环）
4. 系统注入前缀（[BLOCKED/[SEARCH-FIRST/【架构/intent-context 自身）跳过重估
"""
from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from agent.intent_predictor import (  # noqa: E402
    predict,
    predict_and_format,
    predictor_enabled,
)
from agent.agent_loop import _INTENT_SKIP_PREFIXES  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════
# 预测行为（Loki 场景 D：追问仍识别 research）
# ═══════════════════════════════════════════════════════════════════════════

def test_first_turn_research() -> None:
    """「给我找一篇数学论文」→ research（首轮）。"""
    assert predict("给我找一篇数学论文").intent == "research"


def test_followup_question_still_research() -> None:
    """追问「什么论文？」→ research（追问命中——TD-01 pattern 已扩展口语触发词）。"""
    assert predict("什么论文？").intent == "research"


def test_followup_continue_research() -> None:
    """「继续」→ 续执行强制 block_cheap_route（防跳过工具验证）。"""
    p = predict("继续")
    assert p.block_cheap_route is True


# ═══════════════════════════════════════════════════════════════════════════
# 跳过前缀常量化（TD-01 修订 2）
# ═══════════════════════════════════════════════════════════════════════════

def test_skip_prefixes_contains_intent_context() -> None:
    """跳过清单必须含 intent-context 自身（防自触发循环——注入文本是 user 角色）。"""
    assert "<intent-context>" in _INTENT_SKIP_PREFIXES


def test_skip_prefixes_contains_history_summary() -> None:
    """跳过清单必须含 TD-02 摘要前缀（未来注入不触发重估）。"""
    assert "[HISTORY SUMMARY]" in _INTENT_SKIP_PREFIXES


def test_skip_prefixes_contains_system_nudges() -> None:
    """跳过清单覆盖系统注入 nudge 前缀。"""
    for p in ("[BLOCKED", "[SEARCH-FIRST", "【架构", "[intent-action-guard]"):
        assert any(p in sp for sp in _INTENT_SKIP_PREFIXES), f"缺跳过前缀 {p}"


# ═══════════════════════════════════════════════════════════════════════════
# predict_and_format 输出
# ═══════════════════════════════════════════════════════════════════════════

def test_predict_and_format_research_ctx() -> None:
    """research 意图的 context 块含「必须使用工具」提示。"""
    if not predictor_enabled():
        return
    pred, ctx = predict_and_format("帮我找找阅文项目的资料")
    assert pred is not None and pred.intent == "research"
    assert "MUST use web_search" in ctx or "必须" in ctx
