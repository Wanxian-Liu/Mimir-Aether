"""
烟雾测试: SelfEvolutionEngine JEPA框架

验证: Encoder→Cost→Planner→Memory→Engine 全链路
"""
import sys
import os
import time
from pathlib import Path

# 确保 agent/ 在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.self_evolution import (
    StateEncoder, EvolutionCost, EvolutionMemory,
    SafestPathPlanner, SelfEvolutionEngine,
)


def test_encoder_real_files():
    """StateEncoder: 扫描真实 agent/ 目录"""
    encoder = StateEncoder()
    state = encoder.encode(force_refresh=True)

    assert state.total_files > 20, f"Expected >20 files, got {state.total_files}"
    assert state.total_lines > 2000, f"Expected >2000 lines, got {state.total_lines}"
    assert "agent_loop.py" in state.files
    assert "tool_registry.py" in state.files
    print(f"  Encoder: {state.total_files} files, {state.total_lines} lines")


def test_call_graph():
    """构建 agent 内部调用图"""
    encoder = StateEncoder()
    state = encoder.encode(force_refresh=True)

    # 至少有一些文件有内部调用
    has_calls = sum(1 for v in state.call_graph.values() if v)
    assert has_calls > 0, "Expected non-empty call graph"
    print(f"  Call graph: {has_calls} files with internal calls")


def test_reverse_graph():
    """反向调用图: 找出高扇出文件"""
    encoder = StateEncoder()
    state = encoder.encode(force_refresh=True)

    fan_outs = {f: len(callers) for f, callers in state.reverse_call_graph.items()}
    top = sorted(fan_outs.items(), key=lambda x: x[1], reverse=True)[:5]

    print(f"  Top fan-out files:")
    for fpath, n in top:
        print(f"    {fpath}: {n} callers")


def test_get_dependents():
    """传递闭包: 改了某文件后哪些文件受影响"""
    encoder = StateEncoder()
    deps = encoder.get_dependents("types.py")
    print(f"  Dependents of types.py: {deps}")


def test_cost_safe_file():
    """EvolutionCost: 安全文件 (非核心) 应通过 IC"""
    cost = EvolutionCost()
    result = cost.evaluate(["skill_evolution.py"], estimated_lines=10)

    assert result.passed, f"skill_evolution.py should be safe, got: {result.ic_violations}"
    print(f"  Cost(skill_evolution.py): IC=0, TC={result.tc_cost:.2f}")


def test_cost_core_file_blocked():
    """EvolutionCost: agent核心文件应被 IC 阻止"""
    cost = EvolutionCost()
    result = cost.evaluate(["agent_loop.py"])

    assert not result.passed, "agent_loop.py should be BLOCKED by IC"
    assert len(result.ic_violations) > 0
    print(f"  Cost(agent_loop.py): IC=∞, violations={result.ic_violations}")


def test_cost_gateway_file_blocked():
    """EvolutionCost: gateway接口文件应被 IC 阻止"""
    cost = EvolutionCost()
    result = cost.evaluate(["exec_mixin.py"])

    assert not result.passed
    print(f"  Cost(exec_mixin.py): IC=∞, violations={result.ic_violations}")


def test_memory_push_query():
    """EvolutionMemory: 记录和查询"""
    mem = EvolutionMemory()
    from agent.self_evolution.memory import EvolutionRecord

    mem.push(EvolutionRecord(
        timestamp=time.time(),
        changes=["skill_evolution.py"],
        ic_cost=0, tc_cost=2.5, total_cost=2.5,
        outcome="success", tier0_result="PASS",
    ))

    history = mem.query_by_file("skill_evolution.py")
    assert len(history) == 1
    assert history[0].outcome == "success"

    stats = mem.get_stats()
    assert stats["total_records"] == 1
    print(f"  Memory: {stats}")


def test_memory_should_retry():
    """EvolutionMemory: 连续失败3次后应放弃"""
    mem = EvolutionMemory()
    from agent.self_evolution.memory import EvolutionRecord

    for _ in range(3):
        mem.push(EvolutionRecord(
            timestamp=time.time(),
            changes=["broken.py"],
            ic_cost=0, tc_cost=1, total_cost=1,
            outcome="failed", tier0_result="FAIL",
        ))

    assert not mem.should_retry("broken.py", max_failures=3)
    assert mem.should_retry("untouched.py")
    print(f"  should_retry(broken): False, should_retry(untouched): True")


def test_planner_sorts_safely():
    """SafestPathPlanner: 安全文件按TC排序"""
    encoder = StateEncoder()
    cost = EvolutionCost(encoder)
    planner = SafestPathPlanner(encoder, cost)

    # 包含核心文件和安全文件的混合列表
    candidates = [
        "skill_evolution.py",
        "context_compressor.py",
        "agent_loop.py",       # IC=∞
        "exec_mixin.py",       # IC=∞
        "test_skill_evolution.py",
        "tool_quality.py",
    ]

    plan = planner.plan(candidates)

    # IC违规应在 violations 中
    assert len(plan.ic_violations) > 0, "Expected IC violations for core files"

    # 安全文件应排好序
    print(f"  Recommended order: {plan.recommended_order}")
    print(f"  IC violations: {plan.ic_violations}")
    print(f"  Safe files: {plan.safe_files}")


def test_engine_analyze():
    """SelfEvolutionEngine.analyze(): 完整分析链路"""
    engine = SelfEvolutionEngine()

    candidates = [
        "skill_evolution.py",
        "tool_quality.py",
        "context_compressor.py",
        "agent_loop.py",  # 应被IC阻塞
    ]

    result = engine.analyze(candidates)

    assert "state" in result
    assert "cost_analysis" in result
    assert "plan" in result
    assert "memory_hints" in result

    print(f"\n  Engine analyze:")
    print(f"    State: {result['state']['total_files']} files")
    print(f"    Recommended: {result['plan']['recommended_order']}")
    print(f"    IC violations: {len(result['plan']['ic_violations'])}")


def test_engine_run_cycle():
    """SelfEvolutionEngine.run_cycle(): 完整闭环"""
    engine = SelfEvolutionEngine()

    candidates = [
        "skill_evolution.py",
        "tool_quality.py",
        "agent_loop.py",  # IC=∞
    ]

    report = engine.run_cycle(candidates)

    assert report.status in ("healthy", "evolved", "blocked")
    assert report.plan is not None
    print(f"\n  Engine cycle:")
    print(f"    Status: {report.status}")
    print(f"    Summary: {report.summary}")
    print(f"    Cycle time: {report.cycle_time_ms:.1f}ms")


# ── main ──
if __name__ == "__main__":
    print("=" * 60)
    print("Self-Evolution Engine — Smoke Tests")
    print("=" * 60)

    tests = [
        ("Encoder: real files", test_encoder_real_files),
        ("Encoder: call graph", test_call_graph),
        ("Encoder: reverse graph", test_reverse_graph),
        ("Encoder: dependents", test_get_dependents),
        ("Cost: safe file", test_cost_safe_file),
        ("Cost: core blocked", test_cost_core_file_blocked),
        ("Cost: gateway blocked", test_cost_gateway_file_blocked),
        ("Memory: push+query", test_memory_push_query),
        ("Memory: should_retry", test_memory_should_retry),
        ("Planner: sort safely", test_planner_sorts_safely),
        ("Engine: analyze", test_engine_analyze),
        ("Engine: run_cycle", test_engine_run_cycle),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  ✅ {name}")
        except Exception as e:
            failed += 1
            print(f"  ❌ {name}: {e}")

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{passed+failed} passed")
    if failed > 0:
        sys.exit(1)
