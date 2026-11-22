"""蒸馏零增告警升级回归（2026-11-16，刘哥批：连续 3 晚 ⇒ 真告警）。

护的是什么事故
--------------
`_delta_alert` 只是日报中段的一行横幅（第 2 行，后面还有 ~13 行），
实证「22 天不动点无人察觉」——信号存在但观看面无结构性强制。
本组用例护三件：①阈值判定（第 3 晚才升）②自愈（增长即降级 + 归档）
③变异点（等长替换必须算「有变化」，防退回长度差口径）。

状态隔离
--------
全部用例 monkeypatch `_mimir_home` 到 tmp_path ⇒ 不碰真实
`data/dream_alert_state.json` / `DREAM_ALARM_UNRESOLVED.md`。
"""
import importlib

import pytest

import agent.dream_memory as dm


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """把数据根指向 tmp，并清掉模块级状态。"""
    monkeypatch.setattr(dm, "_mimir_home", lambda: str(tmp_path))
    return tmp_path


def _zero_diff():
    return {"key_decisions": {"added": [], "removed": [], "kept": 3, "_removed_text": []},
            "learned_patterns": {"added": [], "removed": [], "kept": 2, "_removed_text": []}}


def _grow_diff():
    return {"key_decisions": {"added": ["tid-new"], "removed": [], "kept": 3, "_removed_text": []},
            "learned_patterns": {"added": [], "removed": [], "kept": 2, "_removed_text": []}}


def test_not_escalated_before_threshold(isolated):
    """负控 1（差一晚不报）：连续 2 晚 ⇒ escalated=False，前置块为空串。"""
    dm.record_alert_night(_zero_diff(), today="2026-11-16")
    st = dm.record_alert_night(_zero_diff(), today="2026-11-17")
    assert st["consecutive_zero"] == 2
    assert st["escalated"] is False
    assert dm._escalation_block(st) == ""
    assert not (isolated / "data" / "DREAM_ALARM_UNRESOLVED.md").exists()


def test_escalates_on_third_night(isolated):
    """正控：第 3 晚 ⇒ escalated=True，前置块以 [ALARM] 开头，告警件存在。"""
    dm.record_alert_night(_zero_diff(), today="2026-11-16")
    dm.record_alert_night(_zero_diff(), today="2026-11-17")
    st = dm.record_alert_night(_zero_diff(), today="2026-11-18")
    assert st["consecutive_zero"] == 3
    assert st["escalated"] is True
    assert st["escalated_since"] == "2026-11-16"
    block = dm._escalation_block(st)
    assert block.startswith("[ALARM]")
    assert "3 晚" in block and "2026-11-16" in block
    alarm = isolated / "data" / "DREAM_ALARM_UNRESOLVED.md"
    assert alarm.exists(), "升级后必须留盘告警件"
    assert "连续零增晚数: 3" in alarm.read_text(encoding="utf-8")


def test_resolve_when_growth_resumes(isolated):
    """负控 2（自愈）：升级后一晚有增长 ⇒ 降级 + 归档 + [RESOLVED] 行。"""
    for d in ("2026-11-16", "2026-11-17", "2026-11-18"):
        dm.record_alert_night(_zero_diff(), today=d)
    alarm = isolated / "data" / "DREAM_ALARM_UNRESOLVED.md"
    assert alarm.exists()
    st = dm.record_alert_night(_grow_diff(), today="2026-11-19")
    assert st["escalated"] is False
    assert st["consecutive_zero"] == 0
    assert st["resolved_now"] is True
    block = dm._escalation_block(st)
    assert block.startswith("[RESOLVED]")
    assert not alarm.exists(), "自愈后未解决件必须消失"
    assert (isolated / "data" / "DREAM_ALARM_UNRESOLVED_RESOLVED_2026-11-19.md").exists()


def test_equal_length_replacement_is_not_zero_growth(isolated):
    """变异点：等长替换（条数不变、内容全换）必须判「有变化」⇒ 不计数。

    若实现改回「只比 len()」，本用例必失败 —— 这就是防退化的那条。
    """
    old_kd = [{"decision": "决策甲"}]
    new_kd = [{"decision": "决策乙"}]
    assert len(old_kd) == len(new_kd)
    d = dm._diff_memory_arrays(old_kd, [], new_kd, [])
    st = dm.record_alert_night(d, today="2026-11-16", persist=False)
    assert st["consecutive_zero"] == 0, "等长替换被当成零增 ⇒ 计数误增"
    assert st["history"][-1]["changed"] is True


def test_dry_run_does_not_persist(isolated):
    """dry_run 不得写状态（否则试跑会污染真实计数）。"""
    st = dm.record_alert_night(_zero_diff(), today="2026-11-16", persist=False)
    assert st["consecutive_zero"] == 1
    assert not (isolated / "data" / "dream_alert_state.json").exists()


def test_prepend_makes_alarm_first_line(isolated):
    """前置：告警块拼在报告标题之前 ⇒ 首行即告警，不在中段。"""
    for d in ("2026-11-16", "2026-11-17", "2026-11-18"):
        st = dm.record_alert_night(_zero_diff(), today=d)
    report = f"{dm._escalation_block(st)}🔄 梦境蒸馏完成\n  - key_decisions: 18 → 18 (+0)\n"
    first = report.splitlines()[0]
    assert first.startswith("[ALARM]"), f"首行不是告警: {first[:40]}"
