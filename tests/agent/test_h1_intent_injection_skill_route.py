"""H-1 回归锁（2026-10-04 · Mimir）——注入块不得触发 skill-route 假命中。

根因（实证）：`search_first_guard._INJECTED_USER_PREFIXES` 漏了 `<intent-context>` ⇒
每轮 intent 注入块被 `last_user_text` 当真实用户消息返回（其标签名自身含 "context"）
⇒ 路由正则裸词 `context` 命中 ⇒ 生产 544 次注入里 508 次（93%）恒推同一个技能。

四组受控差分：A 负控（无 context）· B 目标（真消息+注入块）· C 正控（真谈压缩）· D 纯注入块。
"""

from agent.search_first_guard import (
    is_injected_user_message,
    last_user_text,
)
from agent.skill_scenario_router import (
    recommend_skills,
    should_inject_skill_route_nudge,
    skill_route_satisfied_since_last_user,
)

INTENT_BLOCK = (
    "<intent-context>\n"
    "intent=code complexity=complex confidence=0.75\n"
    "Prefer session_search (or read_file) before answering from memory alone.\n"
    "</intent-context>"
)

COMPRESSOR = "mimiraether-context-compressor"


# ── R1：判据本身覆盖 intent 注入块 ────────────────────────────────────────────


def test_intent_block_recognized_as_injection():
    assert is_injected_user_message(INTENT_BLOCK) is True


def test_plain_user_message_not_injection():
    assert is_injected_user_message("帮我看下 git 状态") is False


def test_chinese_bracket_injections_recognized():
    for prefix in ("【空跑闸门】本 run 已连续 4 轮只读", "【读闸】你已重复读取", "【架构产出提示】"):
        assert is_injected_user_message(prefix) is True, prefix


def test_last_user_text_skips_intent_block():
    msgs = [
        {"role": "user", "content": "帮我看下 git 状态"},
        {"role": "user", "content": INTENT_BLOCK},
    ]
    assert last_user_text(msgs) == "帮我看下 git 状态"


# ── 四组受控差分 ─────────────────────────────────────────────────────────────


def test_A_negative_control_no_context_no_route():
    """A 负控：证明探针非恒真（无 context 就不该命中）。"""
    msgs = [{"role": "user", "content": "帮我看下 git 状态"}]
    ok, skills = should_inject_skill_route_nudge(msgs)
    assert recommend_skills(last_user_text(msgs)) == []
    assert ok is False
    assert skills == []


def test_B_real_message_plus_intent_block_not_routed():
    """B 目标（H-1 病灶）：修复前为 True/[compressor]（假命中）。"""
    msgs = [
        {"role": "user", "content": "帮我看下 git 状态"},
        {"role": "user", "content": INTENT_BLOCK},
    ]
    ok, skills = should_inject_skill_route_nudge(msgs)
    assert ok is False, "注入块不该触发路由（修复前恒 True）"
    assert skills == []


def test_C_real_compression_message_still_routed():
    """C 正控：真谈压缩仍必须命中（防 R3 收紧过度⇒修复变哑）。"""
    msgs = [
        {"role": "user", "content": "上下文压缩阈值要不要调"},
        {"role": "user", "content": INTENT_BLOCK},
    ]
    ok, skills = should_inject_skill_route_nudge(msgs)
    assert ok is True
    assert COMPRESSOR in skills


def test_D_intent_block_alone_not_routed():
    """D：只有注入块（无真实消息）⇒ 不该路由。"""
    msgs = [{"role": "user", "content": INTENT_BLOCK}]
    assert last_user_text(msgs) == ""
    ok, skills = should_inject_skill_route_nudge(msgs)
    assert ok is False
    assert skills == []


# ── R2：已加载技能后，注入块不得让判据"看不见"加载 ──────────────────────────


def test_satisfied_after_skill_view_despite_intent_block():
    """R2 病灶：修复前 slice 从注入块起 ⇒ 此前已加载的技能不算 ⇒ 恒重复注入。"""
    msgs = [
        {"role": "user", "content": "上下文超长了帮我压缩"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": "skill_view",
                                              "arguments": '{"name": "mimiraether-context-compressor"}'}}
        ]},
        {"role": "tool", "name": "skill_view", "content": "loaded mimiraether-context-compressor body"},
        {"role": "user", "content": INTENT_BLOCK},
    ]
    assert skill_route_satisfied_since_last_user(msgs, [COMPRESSOR]) is True
    ok, _ = should_inject_skill_route_nudge(msgs)
    assert ok is False, "已加载过 ⇒ 不该再注入（修复前恒 True）"


def test_skill_view_via_tool_result_satisfies_without_intent_block():
    """负控：同形态但无注入块，行为不变（证明修复未改变原语义）。"""
    msgs = [
        {"role": "user", "content": "上下文超长了帮我压缩"},
        {"role": "tool", "name": "skill_view", "content": "loaded mimiraether-context-compressor body"},
    ]
    assert skill_route_satisfied_since_last_user(msgs, [COMPRESSOR]) is True


# ── R3：正则收紧（裸词 context 不再命中，压缩语义仍在） ──────────────────────


def test_bare_word_context_no_longer_routes():
    """裸 context（如标签残片）不该再触发——原正则裸词是误伤的放大器。"""
    assert COMPRESSOR not in recommend_skills("<intent-context>intent=code</intent-context>")


def test_compression_semantics_preserved():
    for text in ("上下文超长了帮我压缩", "context compress 阈值", "compressor 咋配"):
        assert COMPRESSOR in recommend_skills(text), text
