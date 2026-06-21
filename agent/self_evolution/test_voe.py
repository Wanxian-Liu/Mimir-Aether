"""
EV-VOE05: VoE 检测器场景测试
5 场景：正常/异常/边界/无历史/空文件列表
"""
from agent.self_evolution.voe_detector import VoEDetector
from agent.self_evolution.memory import EvolutionMemory, EvolutionRecord
import time


def test_normal_single_file():
    """T1: 正常单文件改动 → safe"""
    m = _build_history()
    d = VoEDetector().fit(m)
    r = d.detect(["agent/skill_evolution.py"])
    assert r["level"] == "safe", f"Expected safe, got {r['level']}: {r}"
    assert r["surprise_score"] < 0.3, f"Score {r['surprise_score']} >= 0.3"
    print(f"T1 PASS: normal → {r['level']} (score={r['surprise_score']})")


def test_unusual_cross_module():
    """T2: 异常跨模块5文件 → unusual"""
    m = _build_history()
    d = VoEDetector().fit(m)
    r = d.detect([
        "agent/agent_loop.py",
        "gateway/run.py",
        "tools/registry.py",
        "skills/xx.py",
        "tests/yy.py",
    ])
    assert r["level"] in ("caution", "unusual"), f"Expected caution/unusual, got {r['level']}"
    assert r["surprise_score"] > 0.3, f"Score {r['surprise_score']} <= 0.3"
    print(f"T2 PASS: unusual → {r['level']} (score={r['surprise_score']})")


def test_borderline_two_files():
    """T3: 2文件跨模块（历史已有 agent+gateway） → safe or caution"""
    m = _build_history()
    d = VoEDetector().fit(m)
    r = d.detect(["agent/skill_evolution.py", "gateway/config.py"])
    assert r["level"] in ("safe", "caution")
    assert 0.0 <= r["surprise_score"] <= 1.0
    print(f"T3 PASS: borderline → {r['level']} (score={r['surprise_score']})")


def test_no_history():
    """T4: 无历史记录 → safe (fail-open)"""
    d = VoEDetector()  # not fitted
    r = d.detect(["agent/anything.py"])
    assert r["level"] == "safe"
    assert r["surprise_score"] == 0.0
    print(f"T4 PASS: no history → {r['level']} (score={r['surprise_score']})")


def test_empty_files():
    """T5: 空文件列表 → safe"""
    m = _build_history()
    d = VoEDetector().fit(m)
    r = d.detect([])
    assert r["level"] == "safe"
    print(f"T5 PASS: empty → {r['level']} (score={r['surprise_score']})")


def _build_history() -> EvolutionMemory:
    m = EvolutionMemory()
    records = [
        (["agent/skill_evolution.py"], "success"),
        (["agent/config.py"], "success"),
        (["agent/skill_evolution.py", "agent/types.py"], "success"),
        (["tools/mimir_tool.py"], "failed"),
        (["agent/skill_evolution.py"], "success"),
        (["agent/context_compressor.py"], "success"),
        (["agent/tool_port.py", "tools/registry.py"], "failed"),
        (["agent/skill_evolution.py"], "success"),
        (["gateway/run.py", "agent/exec_mixin.py"], "failed"),
        (["agent/skill_evolution.py"], "success"),
    ]
    for i, (files, outcome) in enumerate(records):
        m.push(EvolutionRecord(
            timestamp=time.time() - 1000 + i * 100,
            changes=files,
            ic_cost=0.0, tc_cost=0.5, total_cost=0.5,
            outcome=outcome,
        ))
    return m


if __name__ == "__main__":
    test_normal_single_file()
    test_unusual_cross_module()
    test_borderline_two_files()
    test_no_history()
    test_empty_files()
    print("\n✅ ALL 5 TESTS PASSED")
