"""Tests for agent.skill_scenario_router (BRAIN-11)."""

from agent.skill_scenario_router import (
    MARKER,
    build_skill_route_nudge,
    recommend_skills,
    should_inject_skill_route_nudge,
    skill_route_nudge_enabled,
    skill_route_satisfied_since_last_user,
)


def test_recommend_self_audit_triggers():
    skills = recommend_skills("你进步了吗？变强了吗")
    assert "mimiraether-self-audit" in skills


def test_recommend_debug_triggers():
    skills = recommend_skills("tier0 失败了，帮我找根因")
    assert "mimiraether-root-cause-debugging" in skills


def test_recommend_task_chain_triggers_ship():
    skills = recommend_skills("继续 BRAIN-01 下一粒")
    assert "mimiraether-ship" in skills


def test_build_nudge_contains_marker_and_skills():
    nudge = build_skill_route_nudge(["mimiraether-self-audit"])
    assert MARKER in nudge
    assert "mimiraether-self-audit" in nudge


def test_should_inject_when_not_satisfied():
    messages = [{"role": "user", "content": "你现在的状态怎么样"}]
    ok, skills = should_inject_skill_route_nudge(messages)
    assert ok is True
    assert "mimiraether-self-audit" in skills


def test_satisfied_after_skill_view_tool():
    messages = [
        {"role": "user", "content": "你进步了吗"},
        {
            "role": "tool",
            "name": "skill_view",
            "content": "loaded mimiraether-self-audit body",
        },
    ]
    assert skill_route_satisfied_since_last_user(
        messages, ["mimiraether-self-audit"]
    )
    ok, _ = should_inject_skill_route_nudge(messages)
    assert ok is False


def test_recommend_multi_step():
    s = recommend_skills("刘哥拍板主执行 SELF-02")
    assert "mimiraether-brainstorming" in s
    assert "mimiraether-strategic-planner" in s


def test_recommend_evolution():
    assert "mimiraether-self_evolution" in recommend_skills("跑自我进化")


def test_disabled_via_env(monkeypatch):
    monkeypatch.setenv("MIMIR_SKILL_ROUTE_NUDGE", "0")
    assert skill_route_nudge_enabled() is False
    messages = [{"role": "user", "content": "你进步了吗"}]
    ok, skills = should_inject_skill_route_nudge(messages)
    assert ok is False
    assert skills == []
