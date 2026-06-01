"""ENG-WF-04: Fabrication guard tests — detect claim-without-tool-evidence patterns."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_AGENT_TESTS = Path(__file__).resolve().parent
if str(_AGENT_TESTS) not in sys.path:
    sys.path.insert(0, str(_AGENT_TESTS))

from agent.intent_action_guard import (
    assistant_defers_or_fakes_completion,
    build_nudge_message,
    should_block_text_only_finish,
)


def test_detects_fabrication_claim_without_tool_result():
    """Acceptance-1: '已完成/已读' without role=tool → flagged."""
    msgs = [{"role": "user", "content": "对齐playbook 勾选"}]
    # 已完成宣称 + 无 tool → should_block = True
    assert assistant_defers_or_fakes_completion("已完成对齐，§2c 已勾选")
    assert should_block_text_only_finish(
        msgs, "已完成对齐，§2c 已勾选", has_tool_schemas=True
    )
    # 已经读宣称
    assert assistant_defers_or_fakes_completion("已经读过了，没有问题")


def test_allows_legitimate_tool_grounded_claim():
    """Acceptance-2: '已核对' + role=tool present → not flagged."""
    msgs = [
        {"role": "user", "content": "对齐playbook 勾选"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "1",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "docs/MIMIR_EV_L_INDUSTRIAL_LEARNING.md"}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "1", "content": "§2c = [x][x][x]"},
    ]
    # session_tools_used → True → should_block returns False
    assert not should_block_text_only_finish(
        msgs, "§2c 已全部勾选。", has_tool_schemas=True
    )


def test_fabrication_nudge_marker_differs_from_preemptive():
    """Acceptance-3: fabrication nudge marker ≠ preemptive marker (IQ-33)."""
    nudge = build_nudge_message()
    assert "[intent-action-guard]" in nudge
    # IQ-33: preemptive nudges use a different marker
    assert "[preemptive]" not in nudge
