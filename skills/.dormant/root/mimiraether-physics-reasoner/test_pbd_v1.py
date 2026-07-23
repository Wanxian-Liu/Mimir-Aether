"""
颗粒 2 (PBD) 专项测试 — 碰撞穿透 + 关节约束 + 多体稳定性

五维验证:
  T1: 碰撞检测正确 (两球靠近 → 推开)
  T2: 穿透深度 (<0.001m 高速对撞)
  T3: 能量守恒 (弹性碰撞 KE 守恒)
  T4: 关节约束 (双摆关节稳如磐石)
  T5: 多体稳定性 (无 NaN / 无爆炸)
"""
import numpy as np
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world_model_engine import WorldModelEngine, RigidBody

RESULTS = {}
PASSES = {}

print("=" * 60)
print("颗粒2 (PBD) 五维深度验证")
print("=" * 60)

# ===== T1: 碰撞检测 & 响应 =====
print("\n--- T1: 两球低速对撞 ---")
eng = WorldModelEngine(dt=0.001, method='RK4')
eng.gravity = np.array([0., 0., 0.])  # 零重力
b1 = RigidBody(mass=1.0, position=[0., 0., 0.], velocity=[1.0, 0., 0.])
b2 = RigidBody(mass=1.0, position=[3., 0., 0.], velocity=[-1.0, 0., 0.])
eng.add_body(b1); eng.add_body(b2)
eng.add_collision_pair(0, 1, radius1=0.5, radius2=0.5, restitution=1.0)
res = eng.simulate(duration=3.0)
s = res['states']

# 提取两球位置
p1 = s[:, 0:3]; p2 = s[:, 6:9]
v1 = s[:, 3:6]; v2 = s[:, 9:12]
dist = np.linalg.norm(p1 - p2, axis=1)
min_dist = np.min(dist)

# 检查: 最小距离 >= 0.999 (两半径之和, 允许微小穿透)
T1a = min_dist >= 0.99
# 检查: 碰撞后速度反转 (弹性碰撞, 等质量: v1→v2, v2→v1)
v1_after = v1[-1, 0]
v2_after = v2[-1, 0]
T1b = abs(v1_after - (-1.0)) < 0.05 and abs(v2_after - 1.0) < 0.05

PASSES['T1a_dist'] = T1a
PASSES['T1b_recoil'] = T1b

print(f"  T1a min_dist = {min_dist:.4f}m (期望 ≥ 0.99) → {'PASS' if T1a else 'FAIL'}")
print(f"  T1b v1_after = {v1_after:.3f}, v2_after = {v2_after:.3f} (期望 -1.0 / +1.0) → {'PASS' if T1b else 'FAIL'}")

# ===== T2: 高速对撞穿透深度 =====
print("\n--- T2: 高速对撞穿透测试 ---")
eng = WorldModelEngine(dt=0.001, method='RK4')
eng.gravity = np.array([0., 0., 0.])
b1 = RigidBody(mass=1.0, position=[0., 0., 0.], velocity=[20.0, 1.0, 0.])
b2 = RigidBody(mass=1.0, position=[5., 0., 0.], velocity=[-20.0, 0., 0.])
eng.add_body(b1); eng.add_body(b2)
eng.add_collision_pair(0, 1, radius1=0.5, radius2=0.5, restitution=0.5)
res = eng.simulate(duration=0.5)
s = res['states']
p1 = s[:, 0:3]; p2 = s[:, 6:9]
dist_arr = np.linalg.norm(p1 - p2, axis=1)
min_dist_high = np.min(dist_arr)
penetration = max(0, 1.0 - min_dist_high)  # 1.0 = 半径之和

T2 = penetration < 0.001
PASSES['T2_penetration'] = T2
print(f"  min_dist = {min_dist_high:.6f}m, penetration = {penetration:.6f}m")
print(f"  穿透 < 0.001m → {'PASS' if T2 else 'FAIL'}")

# ===== T3: 弹性碰撞能量守恒 =====
print("\n--- T3: 弹性碰撞能量守恒 ---")
eng = WorldModelEngine(dt=0.001, method='RK4')
eng.gravity = np.array([0., 0., 0.])
b1 = RigidBody(mass=2.0, position=[0., 0., 0.], velocity=[3.0, 0., 0.])
b2 = RigidBody(mass=1.0, position=[5., 0., 0.], velocity=[0., 0., 0.])
eng.add_body(b1); eng.add_body(b2)
eng.add_collision_pair(0, 1, radius1=0.5, radius2=0.5, restitution=1.0)
res = eng.simulate(duration=5.0)
s = res['states']

v1_arr = s[:, 3:6]; v2_arr = s[:, 9:12]
KE = 0.5 * 2.0 * np.sum(v1_arr**2, axis=1) + 0.5 * 1.0 * np.sum(v2_arr**2, axis=1)
KE_initial = KE[0]
KE_before = KE[100]   # 碰撞前 (t≈0.1s)
KE_after = KE[300]    # 碰撞后 (t≈0.3s)
KE_final = KE[-1]

drift = abs(KE_final - KE_initial) / KE_initial * 100
T3 = drift < 1.0
PASSES['T3_energy'] = T3
print(f"  KE_initial = {KE_initial:.4f}J | KE_final = {KE_final:.4f}J")
print(f"  能量漂移 = {drift:.4f}% → {'PASS' if T3 else 'FAIL'}")

# ===== T4: 关节约束 — 双摆关节 =====
print("\n--- T4: 关节约束 (双摆) ---")
eng = WorldModelEngine(dt=0.001, method='RK4')
L1, L2 = 1.0, 1.0
b1 = RigidBody(mass=1.0, position=[L1*np.sin(np.radians(45)), -L1*np.cos(np.radians(45)), 0.])
b2 = RigidBody(mass=1.0, position=[b1.position[0]+L2*np.sin(np.radians(30)), 
                                      b1.position[1]-L2*np.cos(np.radians(30)), 0.])
eng.add_body(b1); eng.add_body(b2)
# 固定锚点
origin = np.array([0., 0., 0.])
eng.add_spring(origin, k=50000.0, natural_length=L1)
# 关节: b1-b2 保持 L2 距离
eng.add_joint(0, 1, stiffness=0.5)
eng.add_collision_pair(0, 1, radius1=0.05, radius2=0.05, restitution=0.0)
res = eng.simulate(duration=3.0)
s = res['states']
p1 = s[:, 0:3]; p2 = s[:, 6:9]
# 检查 b1 到原点距离
d1 = np.linalg.norm(p1 - origin, axis=1)
max_dL1 = np.max(np.abs(d1 - L1))
# 检查 b2 到 b1 距离
d2 = np.linalg.norm(p2 - p1, axis=1)
max_dL2 = np.max(np.abs(d2 - L2))

T4a = max_dL1 < 0.05  # 弹簧约束
T4b = max_dL2 < 0.05  # 关节约束
PASSES['T4a_spring'] = T4a
PASSES['T4b_joint'] = T4b
print(f"  max_dL1 = {max_dL1:.4f}m (期望 < 0.05) → {'PASS' if T4a else 'FAIL'}")
print(f"  max_dL2 (关节) = {max_dL2:.4f}m (期望 < 0.05) → {'PASS' if T4b else 'FAIL'}")

# ===== T5: 多体稳定性 (无 NaN / 无爆炸) =====
print("\n--- T5: 三体稳定性 ---")
eng = WorldModelEngine(dt=0.001, method='RK4')
eng.gravity = np.array([0., -9.8, 0.])
b1 = RigidBody(mass=1.0, position=[0., 5., 0.])
b2 = RigidBody(mass=1.0, position=[0.3, 4., 0.])
b3 = RigidBody(mass=1.0, position=[-0.2, 3., 0.])
eng.add_body(b1); eng.add_body(b2); eng.add_body(b3)
eng.add_collision_pair(0, 1, radius1=0.3, radius2=0.3, restitution=0.5)
eng.add_collision_pair(1, 2, radius1=0.3, radius2=0.3, restitution=0.5)
eng.add_collision_pair(0, 2, radius1=0.3, radius2=0.3, restitution=0.5)
eng.add_ground(y=0.0, restitution=0.3)
res = eng.simulate(duration=3.0)

T5 = 'error' not in res and not np.any(np.isnan(res['states']))
PASSES['T5_stability'] = T5
print(f"  三体 3s 模拟完成 → {'PASS' if T5 else 'FAIL'}")
if 'error' in res:
    print(f"  错误: {res['error']}")

# ===== 汇总 =====
total = len(PASSES)
passed = sum(1 for v in PASSES.values() if v)
RESULTS = {'total': total, 'passed': passed, 'passes': PASSES}

print("\n" + "=" * 60)
print(f"═══ 颗粒2 五维总评: {passed}/{total} ({passed/total*100:.0f}%) ═══")
print("=" * 60)
for k, v in PASSES.items():
    status = 'PASS ✅' if v else 'FAIL 🔴'
    print(f"  {k}: {status}")

if passed == total:
    print("\n✅ 全部通过! PBD 碰撞约束求解器验证成功。")
else:
    print(f"\n⚠️ {total - passed} 项失败，需要修复。")

with open('pbd_v1_results.json', 'w') as f:
    json.dump(RESULTS, f, indent=2)
print("\n结果已保存: pbd_v1_results.json")
