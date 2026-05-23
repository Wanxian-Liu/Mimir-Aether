"""
颗粒 2 (PBD) v2 — 碰撞穿透 + 关节约束 + 多体稳定性 (修复T4)

五维验证:
  T1: 碰撞检测正确
  T2: 高速穿透深度
  T3: 弹性碰撞能量守恒
  T4: 关节约束 (双浮体 + 锚点固定)
  T5: 三体稳定性
"""
import numpy as np, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model_engine import WorldModelEngine, RigidBody

PASSES = {}

print("=" * 60)
print("颗粒2 (PBD) v2 五维深度验证")
print("=" * 60)

# ===== T1: 碰撞检测 & 响应 =====
print("\n--- T1: 两球低速对撞 ---")
eng = WorldModelEngine(dt=0.001, method='RK4')
eng.gravity = np.array([0., 0., 0.])
b1 = RigidBody(mass=1.0, position=[0., 0., 0.], velocity=[1.0, 0., 0.])
b2 = RigidBody(mass=1.0, position=[3., 0., 0.], velocity=[-1.0, 0., 0.])
eng.add_body(b1); eng.add_body(b2)
eng.add_collision_pair(0, 1, radius1=0.5, radius2=0.5, restitution=1.0)
res = eng.simulate(duration=3.0)
s = res['states']; p1 = s[:, 0:3]; p2 = s[:, 6:9]
min_dist = np.min(np.linalg.norm(p1 - p2, axis=1))
v1_after = s[-1, 3]; v2_after = s[-1, 9]
T1a = min_dist >= 0.99
T1b = abs(v1_after + 1.0) < 0.05 and abs(v2_after - 1.0) < 0.05
PASSES['T1a_dist'] = T1a; PASSES['T1b_recoil'] = T1b
print(f"  min_dist={min_dist:.4f}m {'PASS' if T1a else 'FAIL'} | v1={v1_after:.3f} v2={v2_after:.3f} {'PASS' if T1b else 'FAIL'}")

# ===== T2: 高速对撞穿透 =====
print("\n--- T2: 高速对撞穿透 ---")
eng = WorldModelEngine(dt=0.001, method='RK4')
eng.gravity = np.array([0., 0., 0.])
eng.add_body(RigidBody(mass=1.0, position=[0., 0., 0.], velocity=[20., 1., 0.]))
eng.add_body(RigidBody(mass=1.0, position=[5., 0., 0.], velocity=[-20., 0., 0.]))
eng.add_collision_pair(0, 1, 0.5, 0.5, 0.5)
res = eng.simulate(duration=0.5)
s = res['states']
min_d = np.min(np.linalg.norm(s[:, 0:3] - s[:, 6:9], axis=1))
pen = max(0, 1.0 - min_d)
T2 = pen < 0.001
PASSES['T2_penetration'] = T2
print(f"  min_dist={min_d:.6f}m pen={pen:.6f}m → {'PASS' if T2 else 'FAIL'}")

# ===== T3: 弹性碰撞能量守恒 =====
print("\n--- T3: 能量守恒 ---")
eng = WorldModelEngine(dt=0.001, method='RK4')
eng.gravity = np.array([0., 0., 0.])
eng.add_body(RigidBody(mass=2.0, position=[0., 0., 0.], velocity=[3., 0., 0.]))
eng.add_body(RigidBody(mass=1.0, position=[5., 0., 0.], velocity=[0., 0., 0.]))
eng.add_collision_pair(0, 1, 0.5, 0.5, 1.0)
res = eng.simulate(duration=5.0)
s = res['states']
KE = 0.5*2.0*np.sum(s[:, 3:6]**2, axis=1) + 0.5*1.0*np.sum(s[:, 9:12]**2, axis=1)
drift = abs(KE[-1]-KE[0])/KE[0]*100
T3 = drift < 1.0
PASSES['T3_energy'] = T3
print(f"  漂移={drift:.4f}% → {'PASS' if T3 else 'FAIL'}")

# ===== T4: 关节约束 =====
print("\n--- T4a: 双浮体关节 ---")
# 两体自由浮动，关节保持初始距离
eng = WorldModelEngine(dt=0.001, method='RK4')
eng.gravity = np.array([0., -9.8, 0.])
L = 1.0
eng.add_body(RigidBody(mass=1.0, position=[0., 5., 0.], velocity=[2., 0., 0.]))
eng.add_body(RigidBody(mass=1.0, position=[L, 5., 0.], velocity=[0., 0., 0.]))
eng.add_joint(0, 1, stiffness=1.0)
res = eng.simulate(duration=2.0)
s = res['states']; p1 = s[:, 0:3]; p2 = s[:, 6:9]
d12 = np.linalg.norm(p2 - p1, axis=1)
max_dev = np.max(np.abs(d12 - L))
T4a = max_dev < 0.05
PASSES['T4a_joint_float'] = T4a
print(f"  max_dev={max_dev:.4f}m (期望 <0.05) → {'PASS' if T4a else 'FAIL'}")

print("\n--- T4b: 锚点关节 (单摆) ---")
# 体0固定在原点(质量∞)，体1通过关节连接 → 单摆
eng = WorldModelEngine(dt=0.001, method='RK4')
L = 1.0
# 体0 = 锚点 (不移动，通过mass设超大来实现)
eng.add_body(RigidBody(mass=1e10, position=[0., 0., 0.], velocity=[0., 0., 0.]))
eng.add_body(RigidBody(mass=1.0, position=[L*np.sin(0.8), -L*np.cos(0.8), 0.]))
eng.add_joint(0, 1, stiffness=1.0)
res = eng.simulate(duration=3.0)
s = res['states']
p0 = s[:, 0:3]; p1 = s[:, 6:9]
# 锚点应不动
T4b_anchor = np.max(np.abs(p0 - p0[0])) < 0.01
# 摆长应稳定
d01 = np.linalg.norm(p1 - p0, axis=1)
T4b_len = np.max(np.abs(d01 - L)) < 0.05
PASSES['T4b_anchor_fixed'] = T4b_anchor
PASSES['T4b_joint_len'] = T4b_len
print(f"  锚点漂移={np.max(np.abs(p0-p0[0])):.6f}m → {'PASS' if T4b_anchor else 'FAIL'}")
print(f"  摆长偏差={np.max(np.abs(d01-L)):.4f}m → {'PASS' if T4b_len else 'FAIL'}")

# ===== T5: 三体稳定性 =====
print("\n--- T5: 三体稳定性 ---")
eng = WorldModelEngine(dt=0.001, method='RK4')
for i, pos in enumerate([[0.,5.,0.],[0.3,4.,0.],[-0.2,3.,0.]]):
    eng.add_body(RigidBody(mass=1.0, position=pos))
eng.add_collision_pair(0, 1, 0.3, 0.3, 0.5)
eng.add_collision_pair(1, 2, 0.3, 0.3, 0.5)
eng.add_collision_pair(0, 2, 0.3, 0.3, 0.5)
eng.add_ground(y=0.0, restitution=0.3)
res = eng.simulate(duration=3.0)
T5 = 'error' not in res and not np.any(np.isnan(res['states']))
PASSES['T5_stability'] = T5
print(f"  {'PASS' if T5 else 'FAIL'}")

# ===== 汇总 =====
total = len(PASSES); passed = sum(1 for v in PASSES.values() if v)
print("\n" + "=" * 60)
print(f"═══ 颗粒2 v2 总评: {passed}/{total} ({passed/total*100:.0f}%) ═══")
print("=" * 60)
for k, v in PASSES.items():
    print(f"  {k}: {'PASS ✅' if v else 'FAIL 🔴'}")
if passed == total:
    print("\n✅ 全部通过!")
else:
    print(f"\n⚠️ {total-passed} 项失败")

# JSON-safe save
with open('pbd_v2_results.json', 'w') as f:
    json.dump({'total': total, 'passed': passed, 
               'passes': {k: bool(v) for k, v in PASSES.items()}}, f, indent=2)
