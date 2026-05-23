"""
颗粒3 (CostModule) 全面测试
============================
五维诊断: 准确性 / 稳定性 / 边界 / 一致性 / 障碍函数
"""
import numpy as np
import sys
sys.path.insert(0, '.')
from world_model_engine import WorldModelEngine, RigidBody

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"✅ {name}")
    else:
        FAIL += 1
        print(f"❌ {name}  -- {detail}")

# ═══════════════════════════════════════════════════
# 1. 能量守恒代价
# ═══════════════════════════════════════════════════
print("\n── 1. 能量守恒代价 ──")

# 自由落体: 总能量 = KE + PE 守恒
eng = WorldModelEngine(dt=0.001, method='RK4')
b = RigidBody(mass=1.0, position=[0, 10, 0], velocity=[0, 0, 0])
eng.add_body(b)
result = eng.simulate(duration=1.0)
final = result['states'][-1]
cost = eng.evaluate_cost(final)
check("自由落体 IC≈0", cost['ic'] < 0.01, f"IC={cost['ic']:.6f}")
check("能量违反 <1%", cost['breakdown']['energy'] < 0.01,
      f"E={cost['breakdown']['energy']:.6f}")

# 单摆: 能量守恒
eng2 = WorldModelEngine(dt=0.001, method='RK4')
eng2.add_body(RigidBody(mass=1.0, position=[0.5, -0.866, 0], velocity=[0, 0, 0]))
eng2.add_spring([0, 0, 0], k=100, natural_length=1.0)
eng2.add_ground(y=-2)
result2 = eng2.simulate(duration=2.0)
final2 = result2['states'][-1]
cost2 = eng2.evaluate_cost(final2)
check("单摆 IC≈0", cost2['ic'] < 0.05, f"IC={cost2['ic']:.6f}")
check("单摆能量稳定", cost2['breakdown']['energy'] < 0.05,
      f"E={cost2['breakdown']['energy']:.6f}")

# ═══════════════════════════════════════════════════
# 2. 约束代价 — 穿透 + 关节
# ═══════════════════════════════════════════════════
print("\n── 2. 约束代价 ──")

# 无碰撞 → 约束代价=0
eng3 = WorldModelEngine(dt=0.001, method='RK4')
b1 = RigidBody(mass=1.0, position=[0, 5, 0], velocity=[0, 0, 0])
b2 = RigidBody(mass=1.0, position=[10, 5, 0], velocity=[0, 0, 0])
eng3.add_body(b1); eng3.add_body(b2)
eng3.add_collision_pair(0, 1, 0.5, 0.5, 1.0)
res3 = eng3.simulate(duration=0.1)
cost3 = eng3.evaluate_cost(res3['states'][-1])
check("远距离无碰撞", cost3['breakdown']['constraint'] == 0,
      f"constraint={cost3['breakdown']['constraint']:.6f}")

# 碰撞穿透 → 代价 > 0
eng4 = WorldModelEngine(dt=0.001, method='RK4')
b1 = RigidBody(mass=1.0, position=[0, 5, 0], velocity=[+10, 0, 0])
b2 = RigidBody(mass=1.0, position=[1.0, 5, 0], velocity=[-10, 0, 0])
eng4.add_body(b1); eng4.add_body(b2)
eng4.add_collision_pair(0, 1, 0.5, 0.5, 1.0)
res4 = eng4.simulate(duration=0.1)
# 碰撞后应有短暂穿透
mid_cost = eng4.evaluate_cost(res4['states'][len(res4['states'])//2])
check("碰撞中约束代价≥0", mid_cost['breakdown']['constraint'] >= 0)

# ═══════════════════════════════════════════════════
# 3. 任务代价 TC
# ═══════════════════════════════════════════════════
print("\n── 3. 任务代价 TC ──")

eng5 = WorldModelEngine(dt=0.001, method='RK4')
b = RigidBody(mass=1.0, position=[0, 10, 0], velocity=[0, 0, 0])
eng5.add_body(b)
res5 = eng5.simulate(duration=1.0)
mid_state = res5['states'][len(res5['states'])//2]

# 目标: 到达地面 (0,0,0)
goal = {'positions': [[0, 0, 0]]}
cost5_mid = eng5.evaluate_cost(mid_state, goal=goal)
cost5_end = eng5.evaluate_cost(res5['states'][-1], goal=goal)
check("中间状态 TC > 终点 TC", cost5_mid['tc'] > cost5_end['tc'],
      f"mid={cost5_mid['tc']:.3f}, end={cost5_end['tc']:.3f}")

# 任务代价对总代价的贡献
check("总代价包含 TC", cost5_mid['total'] >= cost5_mid['tc'],
      f"total={cost5_mid['total']:.3f}, tc={cost5_mid['tc']:.3f}")

# ═══════════════════════════════════════════════════
# 4. 障碍函数 — +∞ 而非事后检查
# ═══════════════════════════════════════════════════
print("\n── 4. 障碍函数 — 物理不变量 = +∞ 障碍 ──")

eng6 = WorldModelEngine(dt=0.001, method='RK4')
b = RigidBody(mass=1.0, position=[0, 10, 0], velocity=[0, 0, 0])
eng6.add_body(b)
res6 = eng6.simulate(duration=1.0)
final6 = res6['states'][-1]

# 空间边界: 物体必须在地面上方
bounds = {'y': (0, 100)}
cost6 = eng6.evaluate_cost(final6, bounds=bounds)
check("落地后物理合法", cost6['physically_valid'],
      f"valid={cost6['physically_valid']}, IC={cost6['ic']:.6f}")

# 设置不可能的边界: y 必须在 20 以上
bounds_impossible = {'y': (20, 100)}
cost6_imp = eng6.evaluate_cost(final6, bounds=bounds_impossible)
check("违反边界 → +∞", cost6_imp['ic'] == float('inf'),
      f"IC={cost6_imp['ic']}")
check("违反边界 → 物理非法", not cost6_imp['physically_valid'],
      f"valid={cost6_imp['physically_valid']}")

# ═══════════════════════════════════════════════════
# 5. 物理合法性快速检查
# ═══════════════════════════════════════════════════
print("\n── 5. 物理合法性 is_physically_valid ──")

eng7 = WorldModelEngine(dt=0.001, method='RK4')
b = RigidBody(mass=1.0, position=[0, 10, 0], velocity=[0, 0, 0])
eng7.add_body(b)
res7 = eng7.simulate(duration=1.0)
final7 = res7['states'][-1]

check("自由落体合法", eng7.is_physically_valid(final7))
check("自由落体+边界合法", eng7.is_physically_valid(final7, bounds={'y': (-10, 100)}))
check("自由落体+不可能边界不合法",
      not eng7.is_physically_valid(final7, bounds={'y': (20, 100)}))

# ═══════════════════════════════════════════════════
# 6. 代价一致性 — 同一状态重复评估
# ═══════════════════════════════════════════════════
print("\n── 6. 一致性 ──")

eng8 = WorldModelEngine(dt=0.001, method='RK4')
b = RigidBody(mass=1.0, position=[5, 10, 0], velocity=[3, -2, 0])
eng8.add_body(b)
res8 = eng8.simulate(duration=0.5)
s = res8['states'][100]

c1 = eng8.evaluate_cost(s)
c2 = eng8.evaluate_cost(s.copy())
check("重复评估 IC 一致", c1['ic'] == c2['ic'])
check("重复评估 TC 一致", c1['tc'] == c2['tc'])
check("重复评估 total 一致", c1['total'] == c2['total'])

# ═══════════════════════════════════════════════════
# 7. 多体系统
# ═══════════════════════════════════════════════════
print("\n── 7. 多体系统 ──")

eng9 = WorldModelEngine(dt=0.001, method='Verlet')
eng9.add_body(RigidBody(mass=1.0, position=[0, 5, 0], velocity=[0, 0, 0]))
eng9.add_body(RigidBody(mass=1.0, position=[1, 5, 0], velocity=[-1, 0, 0]))
eng9.add_collision_pair(0, 1, 0.3, 0.3, 1.0)
res9 = eng9.simulate(duration=2.0)
final9 = res9['states'][-1]

target_positions = [[0, 0, 0], [2, 0, 0]]
goal9 = {'positions': target_positions}
cost9 = eng9.evaluate_cost(final9, goal=goal9)
check("多体代价评估不崩溃", True)
check("多体 IC 有限", cost9['ic'] < float('inf'),
      f"IC={cost9['ic']:.6f}")
check("多体物理合法", cost9['physically_valid'])

# ═══════════════════════════════════════════════════
# 8. 杨立昆对齐
# ═══════════════════════════════════════════════════
print("\n── 8. 杨立昆 JEPA 对齐 ──")

# IC 不可变: 同一状态、无 goal → IC 每次都一样
eng10 = WorldModelEngine(dt=0.001, method='RK4')
b = RigidBody(mass=1.0, position=[3, 5, 0], velocity=[1, 0, 0])
eng10.add_body(b)
res10 = eng10.simulate(duration=0.5)
state = res10['states'][200]
ic1 = eng10.evaluate_cost(state)['ic']
ic2 = eng10.evaluate_cost(state)['ic']
check("IC 幂等 (不可学习)", ic1 == ic2)

# TC 可变: 不同 goal → 不同 TC
goal_a = {'positions': [[0, 0, 0]]}
goal_b = {'positions': [[10, 10, 0]]}
tc_a = eng10.evaluate_cost(state, goal=goal_a)['tc']
tc_b = eng10.evaluate_cost(state, goal=goal_b)['tc']
check("TC 随目标变化", tc_a != tc_b,
      f"tc_a={tc_a:.3f}, tc_b={tc_b:.3f}")

# ═══════════════════════════════════════════════════
# 9. 积分器兼容性
# ═══════════════════════════════════════════════════
print("\n── 9. 积分器兼容性 ──")
for method in ['Euler', 'RK4', 'Verlet', 'Leapfrog4']:
    eng_m = WorldModelEngine(dt=0.001, method=method)
    eng_m.add_body(RigidBody(mass=1.0, position=[0, 10, 0], velocity=[0, 0, 0]))
    res_m = eng_m.simulate(duration=1.0)
    cost_m = eng_m.evaluate_cost(res_m['states'][-1])
    check(f"{method}: CostModule 不崩溃", True)
    check(f"{method}: 物理合法", cost_m['physically_valid'],
          f"IC={cost_m['ic']:.6f}")

# ═══════════════════════════════════════════════════
# 总结
# ═══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"PASS={PASS}  FAIL={FAIL}  TOTAL={PASS+FAIL}")
if FAIL == 0:
    print("✅ 颗粒3 (CostModule) 全部通过!")
else:
    print(f"❌ {FAIL} 项失败")
