"""LLM+WM Bridge 集成测试 — 候选C端到端验证"""
import sys, numpy as np
sys.path.insert(0, '.')
from llm_wm_bridge import LLMWMBridge, SCENARIOS

PASS, FAIL = 0, 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  ✅ {name}")
    else:
        FAIL += 1; print(f"  ❌ {name}: {detail}")

print("=" * 60)
print("T1: 路由测试 — 关键词匹配")
b = LLMWMBridge()
routes = [
    ("一个球从10m高处掉下来", "free_fall"),
    ("以45度抛出一个炮弹", "projectile"),
    ("单摆的摆动周期", "pendulum"),
    ("两个球撞在一起", "collision_1d"),
    ("物体从斜坡上滑下来", "inclined_plane"),
    ("完全不相关的句子", "free_fall"),  # 默认fallback
]
for desc, expected in routes:
    got = b._route(desc)
    check(f'"{desc[:20]}..." → {expected}', got == expected,
          f"got {got}")

print("\n" + "=" * 60)
print("T2: 自由落体端到端")
r = b.query("一个5kg球从10m落下", mass=5, height=10)
check("场景正确", r['scenario'] == 'free_fall')
check("物理合法", r['physically_valid'])
s = r['summary']
check("有final_state", 'body0' in s.get('final_state', {}))
b0 = s['final_state']['body0']
check("落地y≈0", abs(b0['pos'][1]) < 1e-3, f"y={b0['pos'][1]:.4f}")
check("速度合理", abs(b0['vel'][1]) < 0.1, f"vy={b0['vel'][1]:.2f}")  # restitution=0
check("有解释文本", len(r['explanation']) > 20)
check("无error", 'error' not in r)

print("\n" + "=" * 60)
print("T3: 抛体运动端到端")
r = b.query("以20m/s初速度45度抛出", v0=20, angle=45)
check("场景正确", r['scenario'] == 'projectile')
check("物理合法", r['physically_valid'])
b0 = r['summary']['final_state']['body0']
check("远距离>30m", b0['pos'][0] > 30, f"x={b0['pos'][0]:.1f}")
check("落地y≈0", abs(b0['pos'][1]) < 1e-3)

print("\n" + "=" * 60)
print("T4: 弹性碰撞端到端")
r = b.query("两个球弹性正碰", m1=1, m2=1, v1=1, v2=-1, restitution=1.0)
check("场景正确", r['scenario'] == 'collision_1d')
check("物理合法", r['physically_valid'])
b0 = r['summary']['final_state']['body0']
b1 = r['summary']['final_state']['body1']
check("球1速度交换", abs(b0['vel'][0] - (-1.0)) < 0.1, f"v1={b0['vel'][0]:.3f}")
check("球2速度交换", abs(b1['vel'][0] - 1.0) < 0.1, f"v2={b1['vel'][0]:.3f}")

print("\n" + "=" * 60)
print("T5: 单摆端到端 — Leapfrog4")
r = b.query("一个长1m单摆从30度释放", length=1, angle0=30)
check("场景正确", r['scenario'] == 'pendulum')
check("物理合法", r['physically_valid'])
check("持续>5s", r['summary']['duration_s'] > 5)

print("\n" + "=" * 60)
print("T6: skill_cache — 重复查询走缓存")
b2 = LLMWMBridge()
r1 = b2.query("两个球弹性正碰", m1=1, m2=1, v1=1, v2=-1, restitution=1.0)
r2 = b2.query("两个球弹性正碰", m1=1, m2=1, v1=1, v2=-1, restitution=1.0)
check("两次返回场景相同", r1['scenario'] == r2['scenario'])
# planner的skill_cache在planner里, bridge不涉及, 但bridge的call_count应增加
check("bridge调用计数正确", b2.call_count == 2)

print("\n" + "=" * 60)
print("T7: 成本函数验证")
r = b.query("5kg球从10m落下", mass=5, height=10)
check("有energy_ts数据", len(r['result'].get('energy_ts', [])) > 0)
cost = r['result']
check("有states", len(r['result'].get('states', [])) > 10)

print("\n" + "=" * 60)
print("T8: 所有场景注册完整")
expected_scenarios = {'free_fall', 'projectile', 'pendulum', 'collision_1d', 'collision_2d', 'inclined_plane'}
check("6个场景全部注册", set(SCENARIOS.keys()) == expected_scenarios,
      f"missing: {expected_scenarios - set(SCENARIOS.keys())}")

print("\n" + "=" * 60)
print(f"结果: {PASS} PASS, {FAIL} FAIL  (共 {PASS+FAIL})")
sys.exit(0 if FAIL == 0 else 1)
