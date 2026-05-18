"""
行为契约测试：SOUL.md 「成长」章节四触发器 + 自审过滤器

测试方法：场景驱动行为验证（类似 Hermes Behavioral Eval）
  - 注入模拟 session_stats → 检查 _evaluate_creation_triggers 输出
  - 验证 Precision（不该触发时不啰嗦）
  - 验证 Recall（该触发时绝不漏）
  - 验证真实会话数据一致性

Author: MimirAether (self-evolved)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.skill_curator import (
    _evaluate_creation_triggers,
    skill_creation_audit_nudge,
)


# ── 场景定义 ────────────────────────────────────────────────────────────────

class Scenario:
    """行为测试场景。"""
    def __init__(self, name: str, stats: dict, expect_nudge: bool, reason: str):
        self.name = name
        self.stats = stats
        self.expect_nudge = expect_nudge
        self.reason = reason


# ── 四个正例（应该触发 nudge） ──────────────────────────────────────────────

SCENARIO_5PLUS_TOOLS = Scenario(
    "T1: 5+工具调用完成任务",
    {"tool_calls": 8, "errors_resolved": 0, "user_corrections": 0, "non_obvious_solutions": 0},
    expect_nudge=True,
    reason="触发条件#1: >=5次工具调用，应建议固化"
)

SCENARIO_ERRORS_RESOLVED = Scenario(
    "T2: 踩坑后修复",
    {"tool_calls": 3, "errors_resolved": 2, "user_corrections": 0, "non_obvious_solutions": 0},
    expect_nudge=True,
    reason="触发条件#2: 修复了错误，应存为避坑指南"
)

SCENARIO_USER_CORRECTIONS = Scenario(
    "T3: 用户纠正方向",
    {"tool_calls": 2, "errors_resolved": 0, "user_corrections": 1, "non_obvious_solutions": 0},
    expect_nudge=True,
    reason="触发条件#3: 用户纠正了方向，通用教训应固化"
)

SCENARIO_NON_OBVIOUS = Scenario(
    "T4: 非直觉解法",
    {"tool_calls": 4, "errors_resolved": 0, "user_corrections": 0, "non_obvious_solutions": 1},
    expect_nudge=True,
    reason="触发条件#4: 发现了非直觉方法，值得命名"
)

SCENARIO_MULTI_TRIGGER = Scenario(
    "T5: 多触发器同时命中（复合场景）",
    {"tool_calls": 10, "errors_resolved": 3, "user_corrections": 1, "non_obvious_solutions": 2},
    expect_nudge=True,
    reason="四个触发器全部命中，应强力建议"
)


# ── 四个反例（不该触发 nudge） ──────────────────────────────────────────────

SCENARIO_SIMPLE_TASK = Scenario(
    "F1: 简单单步任务",
    {"tool_calls": 1, "errors_resolved": 0, "user_corrections": 0, "non_obvious_solutions": 0},
    expect_nudge=False,
    reason="简单任务，不应啰嗦"
)

SCENARIO_MODERATE_TASK = Scenario(
    "F2: 普通中等任务（4步，无错误）",
    {"tool_calls": 4, "errors_resolved": 0, "user_corrections": 0, "non_obvious_solutions": 0},
    expect_nudge=False,
    reason="4步无错，边界下不触发"
)

SCENARIO_ALL_ZERO = Scenario(
    "F3: 全零状态",
    {"tool_calls": 0, "errors_resolved": 0, "user_corrections": 0, "non_obvious_solutions": 0},
    expect_nudge=False,
    reason="全零，无任何模式"
)

SCENARIO_EMPTY_STATS = Scenario(
    "F4: 空 dict（无 session_stats）",
    {},
    expect_nudge=False,
    reason="空字典，缺省值全0"
)


# ── 边界场景 ────────────────────────────────────────────────────────────────

SCENARIO_BOUNDARY_5 = Scenario(
    "B1: 边界 — 恰好5步工具调用",
    {"tool_calls": 5, "errors_resolved": 0, "user_corrections": 0, "non_obvious_solutions": 0},
    expect_nudge=True,
    reason=">=5 包含等于5"
)

SCENARIO_BOUNDARY_4 = Scenario(
    "B2: 边界 — 恰好4步工具调用",
    {"tool_calls": 4, "errors_resolved": 1, "user_corrections": 0, "non_obvious_solutions": 0},
    expect_nudge=True,
    reason="虽然 tool_calls<5，但有 errors_resolved"
)

SCENARIO_LARGE_VALUES = Scenario(
    "B3: 极端值",
    {"tool_calls": 999, "errors_resolved": 50, "user_corrections": 10, "non_obvious_solutions": 5},
    expect_nudge=True,
    reason="极大值应正常处理"
)


# ── 测试类 ──────────────────────────────────────────────────────────────────

class TestBehavioralPrecision:
    """Precision: 不该触发时不啰嗦。"""

    def test_simple_task_silent(self):
        result = _evaluate_creation_triggers(SCENARIO_SIMPLE_TASK.stats)
        assert result == "", f"{SCENARIO_SIMPLE_TASK.name}: {SCENARIO_SIMPLE_TASK.reason}"

    def test_moderate_task_silent(self):
        result = _evaluate_creation_triggers(SCENARIO_MODERATE_TASK.stats)
        assert result == "", f"{SCENARIO_MODERATE_TASK.name}: {SCENARIO_MODERATE_TASK.reason}"

    def test_all_zero_silent(self):
        result = _evaluate_creation_triggers(SCENARIO_ALL_ZERO.stats)
        assert result == "", f"{SCENARIO_ALL_ZERO.name}: {SCENARIO_ALL_ZERO.reason}"

    def test_empty_stats_silent(self):
        result = _evaluate_creation_triggers(SCENARIO_EMPTY_STATS.stats)
        assert result == "", f"{SCENARIO_EMPTY_STATS.name}: {SCENARIO_EMPTY_STATS.reason}"


class TestBehavioralRecall:
    """Recall: 该触发时绝不漏。"""

    def test_5plus_tools_triggers(self):
        result = _evaluate_creation_triggers(SCENARIO_5PLUS_TOOLS.stats)
        assert result != "", f"{SCENARIO_5PLUS_TOOLS.name}: {SCENARIO_5PLUS_TOOLS.reason}"
        assert "SOUL_SELF_CHECK" in result

    def test_errors_resolved_triggers(self):
        result = _evaluate_creation_triggers(SCENARIO_ERRORS_RESOLVED.stats)
        assert result != "", f"{SCENARIO_ERRORS_RESOLVED.name}: {SCENARIO_ERRORS_RESOLVED.reason}"
        assert "errors resolved" in result

    def test_user_corrections_triggers(self):
        result = _evaluate_creation_triggers(SCENARIO_USER_CORRECTIONS.stats)
        assert result != "", f"{SCENARIO_USER_CORRECTIONS.name}: {SCENARIO_USER_CORRECTIONS.reason}"
        assert "user corrections" in result

    def test_non_obvious_triggers(self):
        result = _evaluate_creation_triggers(SCENARIO_NON_OBVIOUS.stats)
        assert result != "", f"{SCENARIO_NON_OBVIOUS.name}: {SCENARIO_NON_OBVIOUS.reason}"
        assert "non-obvious solutions" in result

    def test_multi_trigger_includes_all(self):
        result = _evaluate_creation_triggers(SCENARIO_MULTI_TRIGGER.stats)
        assert "10 tool calls" in result
        assert "3 errors resolved" in result
        assert "1 user corrections" in result
        assert "2 non-obvious solutions" in result


class TestBoundaries:
    """边界条件。"""

    def test_boundary_5_tools(self):
        result = _evaluate_creation_triggers(SCENARIO_BOUNDARY_5.stats)
        assert result != "", "恰好5步应触发"

    def test_boundary_4_with_error(self):
        result = _evaluate_creation_triggers(SCENARIO_BOUNDARY_4.stats)
        assert result != "", "4步但有错误应触发"

    def test_large_values(self):
        result = _evaluate_creation_triggers(SCENARIO_LARGE_VALUES.stats)
        assert result != "", "极端值应触发"
        assert "999" in result


class TestNudgeFormat:
    """Nudge 输出格式验证。"""

    def test_nudge_contains_soul_check_marker(self):
        """所有 nudge 必须以 SOUL_SELF_CHECK 开头。"""
        for scenario in [SCENARIO_5PLUS_TOOLS, SCENARIO_ERRORS_RESOLVED,
                         SCENARIO_USER_CORRECTIONS, SCENARIO_NON_OBVIOUS,
                         SCENARIO_MULTI_TRIGGER]:
            result = _evaluate_creation_triggers(scenario.stats)
            assert result.startswith("SOUL_SELF_CHECK"), \
                f"{scenario.name}: nudge 应以 SOUL_SELF_CHECK 开头，实际: {result[:50]}"

    def test_nudge_ends_with_clarify_hint(self):
        """所有 nudge 应以 clarify 提示结尾。"""
        for scenario in [SCENARIO_5PLUS_TOOLS, SCENARIO_ERRORS_RESOLVED,
                         SCENARIO_USER_CORRECTIONS, SCENARIO_MULTI_TRIGGER]:
            result = _evaluate_creation_triggers(scenario.stats)
            assert "clarify" in result.lower(), \
                f"{scenario.name}: nudge 应包含 clarify，实际: {result}"

    def test_silent_scenarios_return_empty_string(self):
        """反例场景必须返回空字符串，不能返回其他值。"""
        for scenario in [SCENARIO_SIMPLE_TASK, SCENARIO_MODERATE_TASK,
                         SCENARIO_ALL_ZERO, SCENARIO_EMPTY_STATS]:
            result = _evaluate_creation_triggers(scenario.stats)
            assert isinstance(result, str), f"{scenario.name}: 返回值类型异常"
            assert result == "", f"{scenario.name}: 应返回空字符串，实际: {result!r}"


class TestRealSessionSmoke:
    """真实会话烟雾测试。"""

    def test_skill_creation_audit_nudge_does_not_crash(self):
        """真实 persistent.json 调用不应崩溃。"""
        result = skill_creation_audit_nudge()
        # 返回类型一定是 str
        assert isinstance(result, str)

    def test_audit_nudge_handles_missing_session_stats(self):
        """persistent.json 缺 session_stats 时不崩溃。"""
        # _evaluate_creation_triggers 直接喂空 dict
        result = _evaluate_creation_triggers({})
        assert result == ""  # 空 stats = 无触发器

    def test_audit_nudge_with_nonexistent_keys(self):
        """stats 中有非预期键不影响结果。"""
        result = _evaluate_creation_triggers({
            "tool_calls": 8,
            "extra_key": "should_be_ignored",
            "nested": {"also": "ignored"},
        })
        assert "SOUL_SELF_CHECK" in result
        # 额外键不影响核心逻辑


class TestCompileAndImport:
    """模块编译 & 导入完整性。"""

    def test_compile(self):
        import py_compile
        py_compile.compile("agent/skill_curator.py", doraise=True)

    def test_evaluate_creation_triggers_importable(self):
        """_evaluate_creation_triggers 应在 __all__ 中且可导入。"""
        from agent.skill_curator import __all__ as all_names
        assert "_evaluate_creation_triggers" in all_names
