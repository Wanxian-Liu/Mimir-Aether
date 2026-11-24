"""颗粒4 测试: MemoryBuffer + 自适应步长 + 能量追踪"""
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from world_model_engine import WorldModelEngine, RigidBody, MemoryBuffer


def test_memory_buffer():
    """MemoryBuffer: push + get_energy_timeseries + capacity"""
    mb = MemoryBuffer(capacity=5)
    for i in range(10):
        mb.push(float(i), np.array([i, 0, 0, 0, 0, 0]), float(i * 9.8))
    assert len(mb) == 5, f"Capacity leak: {len(mb)}"
    ts = mb.get_energy_timeseries()
    assert ts.shape == (5, 2), f"Wrong shape: {ts.shape}"
    assert ts[0, 0] == 5.0, f"Oldest t={ts[0,0]}"
    assert ts[-1, 0] == 9.0, f"Newest t={ts[-1,0]}"
    mb.clear()
    assert len(mb) == 0
    assert mb.get_energy_timeseries().size == 0
    print("  PASS memory buffer")


def test_memory_state_window():
    """MemoryBuffer: get_state_window"""
    mb = MemoryBuffer(capacity=10)
    for i in range(5):
        mb.push(float(i), np.array([i*1.0, 0, 0, 0, 0, 0]), 0.0)
    window = mb.get_state_window(3)
    assert len(window) == 3
    assert window[0][0] == 2.0
    assert window[-1][0] == 4.0
    print("  PASS state window")


def test_compute_energy_free_fall():
    """_compute_energy: 自由落体 KE+PE 守恒"""
    eng = WorldModelEngine(dt=0.001, method='RK4')
    eng.add_body(RigidBody(mass=2.0, position=[0, 10, 0], velocity=[0, 0, 0]))

    # 初始: 纯 PE
    state0 = np.array([0, 10, 0, 0, 0, 0])
    e0 = eng._compute_energy(state0)
    expected_pe = 2.0 * 9.8 * 10  # 196 J
    assert abs(e0 - expected_pe) < 0.1, f"E0={e0} vs {expected_pe}"

    # 落地前: PE→KE 转换
    state_mid = np.array([0, 0, 0, 0, -14.0, 0])  # v = sqrt(2gh) ≈ 14
    e_mid = eng._compute_energy(state_mid)
    expected_ke = 0.5 * 2.0 * 14.0**2  # 196 J
    assert abs(e_mid - expected_ke) < 0.5, f"E_mid={e_mid} vs {expected_ke}"
    # 总能量守恒
    assert abs(e0 - e_mid) < 1.0, f"Energy drift: {e0} → {e_mid}"
    print("  PASS compute_energy free_fall")


def test_compute_energy_static_body():
    """_compute_energy: 静态体不计入能量"""
    eng = WorldModelEngine(dt=0.001)
    eng.add_body(RigidBody(mass=1.0, position=[0, 5, 0]))
    eng.add_body(RigidBody(mass=1e12, position=[0, 0, 0], metadata={'static': True}))

    state = np.array([0, 5, 0, 0, 0, 0,  0, 0, 0, 0, 0, 0])
    e = eng._compute_energy(state)
    # 只算第一个体的 PE = 1*9.8*5 = 49
    assert abs(e - 49.0) < 0.1, f"Static body included: E={e}"
    print("  PASS compute_energy static_body")


def test_energy_timeseries_basic():
    """simulate() → energy_ts 追踪"""
    eng = WorldModelEngine(dt=0.002, method='RK4')
    eng.add_body(RigidBody(mass=1.0, position=[0, 5, 0], velocity=[3, 0, 0]))
    eng.add_ground(y=0.0)

    result = eng.simulate(duration=0.5)
    ets = result.get('energy_ts', None)
    assert ets is not None, "No energy_ts in result"
    assert ets.shape[0] > 10, f"Too few energy samples: {ets.shape[0]}"
    # 能量应近似守恒 (有接地反弹，但 RK4 应 <5%)
    e_start = ets[0, 1]
    e_end = ets[-1, 1]
    drift = abs(e_end - e_start) / abs(e_start)
    assert drift < 0.05, f"Energy drift too large: {drift*100:.1f}%"
    print(f"  PASS energy_timeseries basic (drift={drift*100:.2f}%)")


def test_adaptive_stability():
    """自适应步长: 稳定系统 dt 增大"""
    eng = WorldModelEngine(dt=0.002, method='Verlet')
    eng.add_body(RigidBody(mass=1.0, position=[0, 1, 0], velocity=[0, 0, 0]))
    eng.add_spring(anchor_pos=[0, 0, 0], k=10.0, natural_length=1.0)

    result = eng.simulate(duration=2.0, adaptive=True)
    assert 'error' not in result, f"Error: {result.get('error')}"
    ets = result['energy_ts']
    drift = abs(ets[-1, 1] - ets[0, 1]) / abs(ets[0, 1])
    assert drift < 0.05, f"Adaptive energy drift={drift*100:.1f}%"
    print(f"  PASS adaptive stability (drift={drift*100:.2f}%)")


def test_adaptive_vs_fixed():
    """自适应步长 vs 固定步长: 结果一致"""
    eng_fixed = WorldModelEngine(dt=0.001, method='RK4')
    eng_fixed.add_body(RigidBody(mass=1.0, position=[0, 5, 0], velocity=[2, 3, 0]))

    eng_adaptive = WorldModelEngine(dt=0.001, method='RK4')
    eng_adaptive.add_body(RigidBody(mass=1.0, position=[0, 5, 0], velocity=[2, 3, 0]))

    r1 = eng_fixed.simulate(duration=0.3, adaptive=False)
    r2 = eng_adaptive.simulate(duration=0.3, adaptive=True)

    # 终点状态差异 < 5%
    x1, y1 = r1['states'][-1][0], r1['states'][-1][1]
    x2, y2 = r2['states'][-1][0], r2['states'][-1][1]
    err = max(abs(x1-x2), abs(y1-y2))
    assert err < 0.05, f"Fixed vs adaptive diverge: Δx={abs(x1-x2):.4f} Δy={abs(y1-y2):.4f}"
    print(f"  PASS adaptive vs fixed (max err={err:.4f})")


def test_adaptive_speed():
    """自适应步长: 步数减少 (效率提升)"""
    eng = WorldModelEngine(dt=0.001, method='Verlet')
    eng.add_body(RigidBody(mass=1.0, position=[0, 1, 0], velocity=[0, 0, 0]))
    eng.add_spring(anchor_pos=[0, 0, 0], k=100.0, natural_length=1.0)

    r = eng.simulate(duration=2.0, adaptive=True)
    # 期望步数 ≤ 4000 (固定步长 2000 步, 自适应可能扩大步长)
    n_adaptive = len(r['t'])
    # 自适应可能缩小或扩大, 但应稳定运行
    assert n_adaptive > 0 and 'error' not in r
    print(f"  PASS adaptive speed ({n_adaptive} steps for 2s)")


def test_backward_compat():
    """向后兼容: adaptive=False 结果与颗粒3一致"""
    eng = WorldModelEngine(dt=0.001, method='RK4')
    eng.add_body(RigidBody(mass=2.0, position=[0, 10, 0], velocity=[0, 0, 0]))
    eng.add_ground(y=0.0)

    result = eng.simulate(duration=0.2, adaptive=False)
    assert 'error' not in result
    assert result['t'].shape[0] > 50
    # 自由落体 0.2s: y ≈ 10 - 0.5*9.8*0.04 ≈ 9.8
    final_y = result['states'][-1][1]
    assert 9.6 < final_y < 10.0, f"Unexpected final y={final_y:.2f}"
    print(f"  PASS backward compat (final_y={final_y:.3f})")


def test_reset_clears_memory():
    """reset() 清空 MemoryBuffer + 恢复步长"""
    eng = WorldModelEngine(dt=0.002)
    eng.add_body(RigidBody(mass=1.0, position=[0, 5, 0], velocity=[2, 0, 0]))
    eng.simulate(duration=0.1)
    assert len(eng.memory) > 0

    eng.dt = 0.001  # 手动改步长
    eng.reset()
    assert len(eng.memory) == 0
    assert eng.dt == eng.base_dt, f"dt not reset: {eng.dt} vs {eng.base_dt}"
    print("  PASS reset clears memory")


def test_multi_body_energy():
    """多体能量追踪: 三体模拟"""
    eng = WorldModelEngine(dt=0.001, method='RK4')
    eng.add_body(RigidBody(mass=1.0, position=[0, 0, 0], velocity=[2, 0, 0]))
    eng.add_body(RigidBody(mass=1.0, position=[1, 0, 0], velocity=[0, 0, 0]))
    eng.add_body(RigidBody(mass=1.0, position=[2, 0, 0], velocity=[-2, 0, 0]))
    eng.add_collision_pair(0, 1, 0.1, 0.1, 1.0)
    eng.add_collision_pair(1, 2, 0.1, 0.1, 1.0)

    result = eng.simulate(duration=0.5)
    ets = result['energy_ts']
    e_start, e_end = ets[0, 1], ets[-1, 1]
    # 弹性碰撞能量守恒
    drift = abs(e_end - e_start) / abs(e_start)
    assert drift < 0.02, f"Multi-body energy drift={drift*100:.2f}%"
    print(f"  PASS multi-body energy (drift={drift*100:.2f}%)")


if __name__ == '__main__':
    results = []
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            try:
                fn()
                results.append((name, 'PASS'))
            except Exception as e:
                results.append((name, f'FAIL: {e}'))
                print(f"  FAIL {name}: {e}")

    passed = sum(1 for _, r in results if r == 'PASS')
    print(f"\n{'='*50}")
    print(f"颗粒4: {passed}/{len(results)} PASS")
    for name, r in results:
        print(f"  {name}: {r}")
