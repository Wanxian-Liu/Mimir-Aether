"""A3: max_turns 分档解析测试。

覆盖：
  - 分档表：短20 / 中40 / 长90
  - 任务前置声明（中文别名 + 英文 + 自定义数字）
  - 声明剥离（不进模型上下文）
  - 环境变量 MIMIR_MAX_TURNS_TIER 兜底
  - 优先级：声明 > 环境变量 > 默认
  - 短任务用 20 不截断（20 轮内完成的任务不受影响）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.max_turns_tier import TIERS, resolve_max_turns_tier


def test_tier_table() -> None:
    assert TIERS == {"short": 20, "medium": 40, "long": 90}


def test_declare_cn_short() -> None:
    turns, tier, cleaned = resolve_max_turns_tier(
        "[档位:短] 帮我查一下天气", default=90,
    )
    assert turns == 20
    assert tier == "short"
    assert "档位" not in cleaned
    assert "帮我查一下天气" in cleaned


def test_declare_cn_medium() -> None:
    turns, tier, _ = resolve_max_turns_tier("[档位:中] 完成这个中等任务", default=90)
    assert turns == 40
    assert tier == "medium"


def test_declare_cn_long() -> None:
    turns, tier, _ = resolve_max_turns_tier("[档位:长] 深度调研这个课题", default=90)
    assert turns == 90
    assert tier == "long"


def test_declare_en_tier() -> None:
    turns, tier, cleaned = resolve_max_turns_tier("[tier:short] do x", default=90)
    assert turns == 20
    assert tier == "short"
    assert cleaned == "do x"


def test_declare_custom_number() -> None:
    turns, tier, _ = resolve_max_turns_tier("[tier:50] custom budget", default=90)
    assert turns == 50
    assert tier == "custom"


def test_env_var_fallback() -> None:
    os.environ["MIMIR_MAX_TURNS_TIER"] = "short"
    try:
        turns, tier, _ = resolve_max_turns_tier("普通任务，无声明", default=90)
        assert turns == 20
        assert tier == "short"
    finally:
        os.environ.pop("MIMIR_MAX_TURNS_TIER", None)


def test_env_var_numeric() -> None:
    os.environ["MIMIR_MAX_TURNS_TIER"] = "35"
    try:
        turns, tier, _ = resolve_max_turns_tier("任务", default=90)
        assert turns == 35
        assert tier == "custom"
    finally:
        os.environ.pop("MIMIR_MAX_TURNS_TIER", None)


def test_declaration_beats_env() -> None:
    os.environ["MIMIR_MAX_TURNS_TIER"] = "long"
    try:
        turns, tier, _ = resolve_max_turns_tier("[tier:short] 声明优先", default=90)
        assert turns == 20
        assert tier == "short"
    finally:
        os.environ.pop("MIMIR_MAX_TURNS_TIER", None)


def test_default_when_nothing_declared() -> None:
    turns, tier, cleaned = resolve_max_turns_tier("普通任务", default=90)
    assert turns == 90
    assert tier == "default"
    assert cleaned == "普通任务"


def test_invalid_declaration_ignored() -> None:
    # 非法声明值 → 回落到默认，不清洗消息
    turns, tier, cleaned = resolve_max_turns_tier("[档位:超长] 任务", default=90)
    assert turns == 90
    assert tier == "default"
    assert "[档位:超长]" in cleaned  # 非法声明不剥离（避免误删正文）


def test_short_task_not_truncated() -> None:
    """短任务用 20：20 轮内完成的任务不受截断影响（回归）。

    模拟：一次 5 轮即完成的任务，max_turns=20 时 turns_used=5 ≤ 20，
    循环正常结束，不会因 max_turns 提前中断。
    """
    import asyncio
    from agent.agent_loop import MimirAgentLoop

    # TD-03 隔离：本测试验证 max_turns 截断逻辑，不受产出校验环境变量影响
    # （CI 未设置=0；本地开发环境可能开启 MIMIR_PRODUCTION_ENFORCE=1 → L3 中断干扰断言）
    _saved_enforce = os.environ.get("MIMIR_PRODUCTION_ENFORCE")
    os.environ["MIMIR_PRODUCTION_ENFORCE"] = "0"

    turns, tier, _ = resolve_max_turns_tier("[tier:short] 快速任务", default=90)
    assert turns == 20

    called = 0

    class _Msg:
        def __init__(self, content, tool_calls, reasoning_content=None):
            self.content = content
            self.tool_calls = tool_calls
            self.reasoning_content = reasoning_content

    class _Choice:
        def __init__(self, msg):
            self.message = msg

    class _Resp:
        def __init__(self, content, tool_calls):
            self.choices = [_Choice(_Msg(content, tool_calls))]

    async def chat_fn(messages):
        nonlocal called
        called += 1
        if called <= 5:
            return _Resp("step", [{
                "id": f"c{called}", "type": "function",
                "function": {"name": "noop", "arguments": "{}"},
            }])
        return _Resp("done", None)

    async def dispatcher(name, args, task_id):
        return "ok"

    async def main():
        loop = MimirAgentLoop(
            model_call=chat_fn,
            tool_schemas=[],
            valid_tool_names=set(),
            tool_dispatcher=dispatcher,
            max_turns=turns,
        )
        result = await loop.run([
            {"role": "system", "content": "test"},
            {"role": "user", "content": "[tier:short] 快速任务"},
        ])
        return result

    try:
        result = asyncio.run(main())
        assert result.turns_used <= 20
        # 5 tool 轮 + 收尾轮 + 可能的 guard/nudge 注入轮，全部完成未被 20 截断
        assert called >= 6
        assert not result.interrupted
        print(f"[regression] short tier: turns_used={result.turns_used}, called={called} — 未被 20 截断 ✅")
    finally:
        if _saved_enforce is None:
            E.pop("MIMIR_PRODUCTION_ENFORCE", None)
        else:
            os.environ["MIMIR_PRODUCTION_ENFORCE"] = _saved_enforce


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    if passed != len(fns):
        sys.exit(1)
