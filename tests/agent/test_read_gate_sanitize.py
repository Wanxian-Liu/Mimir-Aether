"""
读闸 400 根因修复 · 改动2 单测（2026-08-25 Mimir 修复卡）

覆盖（任务书【WHAT】改动2）：
1. 合成 user 消息插在 assistant(tool_calls) 与 tool 结果之间 → sanitize 后移到序列尾部，API 合法
2. 无插入的正常序列 → 原样保留（不误伤）
3. 多 assistant(tool_calls) 批次 + 多个插入 user → 全部移到尾部
4. 插入 user 在 tool 结果之后（合法位置）→ 不移动
5. 与既有孤儿 tool / 缺失响应规则共存（回归）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.context_compressor import ContextCompressorV2


def _comp(quiet=True):
    return ContextCompressorV2(quiet_mode=quiet)


def _asst(content="", tool_calls=None):
    m = {"role": "assistant", "content": content}
    if tool_calls:
        m["tool_calls"] = tool_calls
    return m


def _tool(tid, content="ok"):
    return {"role": "tool", "tool_call_id": tid, "content": content}


def _tc(tid, name="echo", args='{"a":1}'):
    return {"id": tid, "type": "function",
            "function": {"name": name, "arguments": args}}


def _user(content):
    return {"role": "user", "content": content}


# ============ 1. 核心场景：读闸合成 user 插入在中间 ============
def test_synthetic_user_between_asst_and_tool_moved_to_tail():
    print("\n[RG-1] 合成 user 插在 assistant(tool_calls) 与 tool 结果之间 → 移到尾部")
    msgs = [
        _user("hi"),
        _asst("", [_tc("call_1")]),
        _user("【读闸】你已重复读取 xxx 第 3 次——必须停止读取"),  # 破坏序列的插入
        _tool("call_1"),
    ]
    cleaned = _comp()._sanitize_tool_pairs(list(msgs))
    roles = [m["role"] for m in cleaned]
    # 序列必须变为: user, assistant(tool_calls), tool, user(尾部)
    assert roles == ["user", "assistant", "tool", "user"], f"roles={roles}"
    # 尾部 user 必须是读闸消息
    assert cleaned[-1]["content"].startswith("【读闸】"), f"tail={cleaned[-1]}"
    # assistant 与其 tool 结果之间无任何 user —— API 合法
    for i, m in enumerate(cleaned):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            nxt = cleaned[i + 1]
            assert nxt["role"] == "tool", f"assistant 后必须是 tool, got {nxt}"
    print("  ✅ 序列合法: user → assistant(tool_calls) → tool → user(尾部)")


# ============ 2. 无插入的正常序列 → 原样保留 ============
def test_normal_sequence_untouched():
    print("\n[RG-2] 正常序列（无插入 user）→ 原样保留")
    msgs = [
        _user("hi"),
        _asst("", [_tc("call_1")]),
        _tool("call_1"),
        _asst("done"),
    ]
    cleaned = _comp()._sanitize_tool_pairs(list(msgs))
    assert cleaned == msgs, f"正常序列被改动: {cleaned}"
    print("  ✅ 正常序列未被改动")


# ============ 3. 多批次 + 多插入 → 全部移到尾部 ============
def test_multiple_inserted_users_all_moved():
    print("\n[RG-3] 多批次插入 user → 全部移到尾部（保持相对顺序）")
    msgs = [
        _user("q1"),
        _asst("", [_tc("c1"), _tc("c2")]),
        _user("【读闸】插入1"),
        _tool("c1"),
        _user("【读闸】插入2"),
        _tool("c2"),
    ]
    cleaned = _comp()._sanitize_tool_pairs(list(msgs))
    roles = [m["role"] for m in cleaned]
    assert roles == ["user", "assistant", "tool", "tool", "user", "user"], f"roles={roles}"
    # 两个读闸消息都在尾部
    tails = [m["content"] for m in cleaned if m["role"] == "user"][1:]
    assert tails == ["【读闸】插入1", "【读闸】插入2"], f"tails={tails}"
    print("  ✅ 多插入全部移到尾部，相对顺序保留")


# ============ 4. 合法位置的 user（tool 结果之后）→ 不移动 ============
def test_user_after_tool_result_not_moved():
    print("\n[RG-4] tool 结果之后的 user（合法位置）→ 不移动")
    msgs = [
        _user("q1"),
        _asst("", [_tc("c1")]),
        _tool("c1"),
        _user("follow-up"),  # tool 之后，合法
    ]
    cleaned = _comp()._sanitize_tool_pairs(list(msgs))
    assert cleaned == msgs, f"合法 user 被移动: {cleaned}"
    print("  ✅ 合法位置 user 未被移动")


# ============ 5. 与既有规则共存（孤儿 tool / 缺失响应） ============
def test_coexists_with_existing_rules():
    print("\n[RG-5] 与既有孤儿 tool / 缺失响应规则共存")
    msgs = [
        _user("q1"),
        _asst("", [_tc("c1")]),
        _user("【读闸】插入"),
        _tool("c1"),
        _tool("call_orphan"),  # 孤儿：无前导 tool_calls
    ]
    cleaned = _comp()._sanitize_tool_pairs(list(msgs))
    roles = [m["role"] for m in cleaned]
    # 孤儿 tool 被移除，插入 user 移到尾部
    assert roles == ["user", "assistant", "tool", "user"], f"roles={roles}"
    assert cleaned[-1]["role"] == "user", f"tail={cleaned[-1]}"
    print("  ✅ 孤儿移除 + 插入移动共存正常")


if __name__ == "__main__":
    test_synthetic_user_between_asst_and_tool_moved_to_tail()
    test_normal_sequence_untouched()
    test_multiple_inserted_users_all_moved()
    test_user_after_tool_result_not_moved()
    test_coexists_with_existing_rules()
    print("\n全部通过 ✅")
