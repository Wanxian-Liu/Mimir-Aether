"""EV-PHY01 验收测试 — 5 道经典力学题

验收标准：全部正确返回数值结果 + 推导步骤。
系统路径由 conftest.py 在 collection 前注入。
"""

import os
import tempfile
import pytest
from mimiraether_physics_reasoner.solver import PhysicsSolver, PhysicsQuery
from mimiraether_physics_reasoner.skill_migrator import SkillMigrator


@pytest.fixture
def solver():
    return PhysicsSolver()


@pytest.fixture
def migrator():
    """每个测试独立的 SkillMigrator（临时文件，互不污染）"""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="physics_migrator_test_")
    os.close(fd)
    m = SkillMigrator(cache_path=path)
    yield m
    try:
        os.unlink(path)
    except OSError:
        pass


# ── 验收题 1: 自由落体速度 ──────────────────────────

def test_free_fall_velocity(solver):
    """5kg 球从 10m 落下，落地速度"""
    result = solver.solve(PhysicsQuery(
        domain="kinematics",
        given={"h": 10, "g": 9.8},
        target="velocity",
    ))
    assert result.success, f"求解失败: {result.error}"
    assert abs(result.result - 14.0) < 0.1, f"期望 v≈14.0 m/s，实际 {result.result}"
    assert result.unit == "m/s"
    assert result.formula_used == "free_fall_velocity"
    assert len(result.steps) >= 4
    assert "选定公式" in result.steps[1] or "v = sqrt(2*g*h)" in result.steps[1]


# ── 验收题 2: 斜面加速度 ────────────────────────────

def test_inclined_plane_accel(solver):
    """30° 斜面，摩擦系数 0.2，求加速度"""
    import math
    result = solver.solve(PhysicsQuery(
        domain="dynamics",
        given={"g": 9.8, "theta": math.radians(30), "mu": 0.2},
        target="acceleration",
    ))
    assert result.success, f"求解失败: {result.error}"
    # a = g*(sin30 - mu*cos30) = 9.8*(0.5 - 0.2*0.866) ≈ 3.20
    assert abs(result.result - 3.20) < 0.1, f"期望 a≈3.20 m/s²，实际 {result.result}"
    assert result.unit == "m/s²"
    assert result.formula_used == "inclined_plane_accel_with_friction"


# ── 验收题 3: 弹性碰撞 ──────────────────────────────

def test_elastic_collision(solver):
    """弹性碰撞：m1=2kg v1=3m/s 撞静止 m2=1kg，求 m1 碰后速度"""
    result = solver.solve(PhysicsQuery(
        domain="momentum",
        given={"m1": 2, "m2": 1, "v1_before": 3, "v2_before": 0},
        target="v1_after",
    ))
    assert result.success, f"求解失败: {result.error}"
    # v1_after = ((2-1)*3 + 2*1*0)/(2+1) = 3/3 = 1.0 m/s
    assert abs(result.result - 1.0) < 0.1, f"期望 v1_after=1.0 m/s，实际 {result.result}"
    assert result.unit == "m/s"
    assert "elastic" in result.formula_used


# ── 验收题 4: 弹簧周期 ──────────────────────────────

def test_spring_period(solver):
    """弹簧振子 m=0.5kg k=200N/m，求周期"""
    result = solver.solve(PhysicsQuery(
        domain="kinematics",
        given={"m": 0.5, "k": 200},
        target="period",
    ))
    assert result.success, f"求解失败: {result.error}"
    # T = 2*pi*sqrt(0.5/200) = 2*pi*sqrt(0.0025) = 2*pi*0.05 ≈ 0.314
    assert abs(result.result - 0.314) < 0.01, f"期望 T≈0.314 s，实际 {result.result}"
    assert result.unit == "s"
    assert "spring" in result.formula_used or "period" in result.formula_used


# ── 验收题 5: 抛体水平射程 ──────────────────────────

def test_projectile_range(solver):
    """初速 20m/s，45° 角抛射，求水平射程"""
    import math
    result = solver.solve(PhysicsQuery(
        domain="kinematics",
        given={"v0": 20, "theta": math.radians(45), "g": 9.8},
        target="range",
    ))
    assert result.success, f"求解失败: {result.error}"
    # R = 20²*sin(90°)/9.8 = 400/9.8 ≈ 40.82
    assert abs(result.result - 40.82) < 0.5, f"期望 R≈40.82 m，实际 {result.result}"
    assert result.unit == "m"
    assert "projectile" in result.formula_used


# ── SkillMigrator 测试 ──────────────────────────────

def test_skill_migrator_basic(migrator):
    """基本迁移：3 次自动触发"""
    assert migrator.lookup("kinematics", "velocity", {"h": 10, "g": 9.8}) is None

    triggered = migrator.on_solve("kinematics", "velocity", {"h": 10, "g": 9.8},
                                   14.0, "m/s", "free_fall_velocity",
                                   ["1. 识别", "2. 公式", "3. 代入", "4. 14.0 m/s"])
    assert not triggered

    triggered = migrator.on_solve("kinematics", "velocity", {"h": 10, "g": 9.8},
                                   14.0, "m/s", "free_fall_velocity",
                                   ["1. 识别", "2. 公式", "3. 代入", "4. 14.0 m/s"])
    assert not triggered

    triggered = migrator.on_solve("kinematics", "velocity", {"h": 10, "g": 9.8},
                                   14.0, "m/s", "free_fall_velocity",
                                   ["1. 识别", "2. 公式", "3. 代入", "4. 14.0 m/s"])
    assert triggered

    cached = migrator.lookup("kinematics", "velocity", {"h": 10, "g": 9.8})
    assert cached is not None
    assert abs(cached.result - 14.0) < 0.01
    assert cached.unit == "m/s"


def test_skill_migrator_no_cache_for_diff_params(migrator):
    """不同参数不会命中同一缓存"""
    for _ in range(3):
        migrator.on_solve("kinematics", "velocity", {"h": 10, "g": 9.8},
                          14.0, "m/s", "free_fall_velocity", ["step"])
    assert migrator.lookup("kinematics", "velocity", {"h": 20, "g": 9.8}) is None


def test_skill_migrator_stats(migrator):
    """统计信息正确"""
    for _ in range(5):
        migrator.on_solve("kinematics", "velocity", {"h": 10, "g": 9.8},
                          14.0, "m/s", "free_fall_velocity", ["step"])
    stats = migrator.get_stats()
    assert stats["total_counter_entries"] == 1
    assert stats["total_fast_path_entries"] == 1
    assert stats["fast_path"]["kinematics:velocity:(g=9.8,h=10)"]["count"] == 5


# ── 端到端：System 2 → System 1 完整链路 ──────────

def test_e2e_system2_to_system1(solver, migrator):
    """完整双路径：先走 System 2 完整推导，≥3 次后切 System 1 查表"""
    query = PhysicsQuery(
        domain="kinematics",
        given={"h": 10, "g": 9.8},
        target="velocity",
    )

    for _ in range(2):
        cached = migrator.lookup(query.domain, query.target, query.given)
        assert cached is None
        result = solver.solve(query)
        assert result.success
        migrator.on_solve(query.domain, query.target, query.given,
                          result.result, result.unit,
                          result.formula_used, result.steps)

    cached = migrator.lookup(query.domain, query.target, query.given)
    assert cached is None

    result = solver.solve(query)
    assert result.success
    migrator.on_solve(query.domain, query.target, query.given,
                      result.result, result.unit,
                      result.formula_used, result.steps)

    cached = migrator.lookup(query.domain, query.target, query.given)
    assert cached is not None
    assert abs(cached.result - result.result) < 0.01
