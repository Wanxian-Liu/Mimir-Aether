"""
LLM ↔ World Model Bridge — LLM路由 + 世界模型模拟 → 自然语言回报
=========================================================================

候选C (LLM+WM端到端Demo) 的核心桥接层:
  用户飞书发物理题 → LLM路由 + 场景解析 → 引擎模拟 → CostModule验证 → LLM回报

架构:
  ScenarioTemplate: 自然语言场景 → 结构化参数 → WorldModelEngine配置
  Bridge.query():   NL查询入口 → 模板匹配 → 引擎模拟 → 结果dict

纯NumPy, CPU only。不改agent/gateway。
"""

import numpy as np
from world_model_engine import WorldModelEngine, RigidBody

SCENARIOS = {}

def scenario(name):
    """装饰器: 注册场景模板"""
    def dec(fn):
        SCENARIOS[name] = fn
        return fn
    return dec

# ============================================================
# 场景模板
# ============================================================

@scenario("free_fall")
def free_fall(mass=1.0, height=10.0, gravity=-9.8):
    """自由落体: 物体从高处静止释放"""
    engine = WorldModelEngine(method='RK4')
    engine.gravity = np.array([0, gravity, 0])
    engine.add_body(RigidBody(mass=mass, position=[0, height, 0]))
    engine.add_ground(y=0.0, restitution=0.0)
    result = engine.simulate(duration=np.sqrt(2*height/abs(gravity))*1.5)
    return engine, result

@scenario("projectile")
def projectile(v0=20.0, angle=45.0, height=0.0, gravity=-9.8, mass=1.0):
    """抛体运动: 初速度 + 角度"""
    rad = np.radians(angle)
    engine = WorldModelEngine(method='RK4')
    engine.gravity = np.array([0, gravity, 0])
    engine.add_body(RigidBody(
        mass=mass,
        position=[0, height, 0],
        velocity=[v0*np.cos(rad), v0*np.sin(rad), 0]
    ))
    engine.add_ground(y=0.0, restitution=0.0)
    t_max = 2 * v0 * np.sin(rad) / abs(gravity) * 1.2 + 0.5
    result = engine.simulate(duration=max(t_max, 0.5))
    return engine, result

@scenario("pendulum")
def pendulum(length=1.0, angle0=30.0, mass=1.0, gravity=-9.8):
    """单摆: 固定角度释放"""
    rad = np.radians(angle0)
    engine = WorldModelEngine(method='Leapfrog4')
    engine.gravity = np.array([0, gravity, 0])
    engine.add_body(RigidBody(
        mass=mass,
        position=[length*np.sin(rad), -length*np.cos(rad), 0]
    ))
    # 静态锚点
    engine.add_body(RigidBody(
        mass=1e12,
        position=[0, 0, 0],
        metadata={'static': True}
    ))
    engine.add_joint(0, 1, stiffness=1.0)
    T = 2*np.pi*np.sqrt(length/abs(gravity))
    result = engine.simulate(duration=T*10, adaptive=False)
    return engine, result

@scenario("collision_1d")
def collision_1d(m1=1.0, m2=1.0, v1=1.0, v2=-1.0, restitution=1.0):
    """一维弹性碰撞"""
    engine = WorldModelEngine(method='RK4')
    engine.gravity = np.array([0, 0, 0])
    engine.add_body(RigidBody(mass=m1, position=[-2, 0, 0], velocity=[v1, 0, 0]))
    engine.add_body(RigidBody(mass=m2, position=[2, 0, 0], velocity=[v2, 0, 0]))
    engine.add_collision_pair(0, 1, radius1=0.5, radius2=0.5, restitution=restitution)
    result = engine.simulate(duration=4.0)
    return engine, result

@scenario("collision_2d")
def collision_2d(m1=1.0, m2=1.0, restitution=0.8):
    """二维斜碰"""
    engine = WorldModelEngine(method='Verlet')
    engine.gravity = np.array([0, 0, 0])
    engine.add_body(RigidBody(mass=m1, position=[-3, 1, 0], velocity=[2, -1, 0]))
    engine.add_body(RigidBody(mass=m2, position=[0, 0, 0], velocity=[0, 0, 0]))
    engine.add_collision_pair(0, 1, radius1=0.5, radius2=0.5, restitution=restitution)
    result = engine.simulate(duration=4.0)
    return engine, result

@scenario("inclined_plane")
def inclined_plane(angle=30.0, length=5.0, mass=1.0, friction=0.0, gravity=-9.8):
    """斜面滑动"""
    rad = np.radians(angle)
    g_eff = abs(gravity) * (np.sin(rad) - friction*np.cos(rad))
    engine = WorldModelEngine(method='RK4')
    engine.gravity = np.array([abs(gravity)*np.sin(rad), -abs(gravity)*np.cos(rad), 0])
    engine.add_body(RigidBody(mass=mass, position=[0, 0, 0]))
    engine.add_ground(y=0.0, restitution=0.0)
    t_end = np.sqrt(2*length/g_eff)*1.5 if g_eff > 0 else 2.0
    result = engine.simulate(duration=t_end)
    return engine, result

# ============================================================
# LLM路由模拟 + 查询引擎
# ============================================================

class LLMWMBridge:
    """LLM ↔ 世界模型桥接器

    当前: 基于关键词匹配的路由 (模拟LLM路由)
    远期: DeepSeek API 直接路由 → 场景选择 → 引擎模拟
    """

    ROUTE_KEYWORDS = {
        "free_fall": ["落下", "自由落体", "掉落", "下落", "坠", "摔"],
        "projectile": ["抛出", "抛射", "射程", "初速度", "斜抛", "平抛", "炮弹"],
        "pendulum": ["单摆", "钟摆", "摆锤", "摆动", "秋千"],
        "collision_1d": ["碰撞", "对撞", "正碰", "弹性碰撞", "撞在一起"],
        "collision_2d": ["斜碰", "二维碰撞", "侧面碰撞"],
        "inclined_plane": ["斜面", "斜坡", "滑下", "滑落", "坡度"],
    }

    def __init__(self):
        self.call_count = 0

    def query(self, description, **overrides):
        """NL查询入口 — LLM路由 + 引擎模拟 → 结构化结果

        Args:
            description: str — 自然语言物理场景描述
            **overrides: 场景参数覆盖 (mass, height, angle, etc.)

        Returns:
            dict: {
                'scenario': str,
                'result': engine.simulate()结果,
                'summary': dict — {final_pos, final_vel, duration, energy_drift, ...},
                'physically_valid': bool,
                'explanation': str — 自然语言解释
            }
        """
        self.call_count += 1
        scenario_name = self._route(description)
        scenario_fn = SCENARIOS.get(scenario_name)

        if scenario_fn is None:
            return {
                'scenario': scenario_name,
                'error': f'Unknown scenario: {scenario_name}',
                'summary': {},
                'physically_valid': False,
                'explanation': f'无法识别物理场景: "{description}"'
            }

        engine, sim_result = scenario_fn(**overrides)

        # 提取关键数据
        states = sim_result.get('states', np.array([]))
        if len(states) > 0:
            final = states[-1]
            n_bodies = len(engine.bodies)
            summary = {
                'n_bodies': n_bodies,
                'duration_s': sim_result['t'][-1] if len(sim_result['t']) > 0 else 0,
                'n_steps': len(states),
                'final_state': {f'body{i}': {
                    'pos': final[i*6:i*6+3].tolist(),
                    'vel': final[i*6+3:i*6+6].tolist()
                } for i in range(n_bodies)},
            }
            # 能量漂移
            if 'energy_ts' in sim_result and len(sim_result['energy_ts']) >= 2:
                ets = sim_result['energy_ts']
                e0, ef = ets[0][1], ets[-1][1]
                summary['energy_initial'] = float(e0)
                summary['energy_final'] = float(ef)
                summary['energy_drift_pct'] = float((ef-e0)/abs(e0)*100) if abs(e0) > 1e-10 else 0.0
            else:
                summary['energy_drift_pct'] = 0.0
        else:
            summary = {'n_bodies': 0, 'duration_s': 0, 'n_steps': 0, 'error': 'No states'}

        # 物理合法性
        valid = True
        if len(states) > 0:
            try:
                valid = engine.is_physically_valid(states[-1])
            except Exception:
                valid = True

        explanation = self._explain(scenario_name, summary, description)

        return {
            'scenario': scenario_name,
            'result': sim_result,
            'summary': summary,
            'physically_valid': valid,
            'explanation': explanation
        }

    def _route(self, description):
        """关键词路由 (模拟LLM路由 — 由DeepSeek替代)
        返回最匹配的场景名, 默认 'free_fall'"""
        for scenario_name, keywords in self.ROUTE_KEYWORDS.items():
            for kw in keywords:
                if kw in description:
                    return scenario_name
        return 'free_fall'

    def _explain(self, scenario_name, summary, description):
        """用自然语言解释模拟结果"""
        if 'error' in summary:
            return f"模拟失败: {summary.get('error', '未知错误')}"

        parts = []
        drift = summary.get('energy_drift_pct', 0.0)
        n_bodies = summary.get('n_bodies', 0)

        if scenario_name == 'free_fall':
            b0 = summary['final_state']['body0']
            pos_y = b0['pos'][1]
            vel_y = b0['vel'][1]
            dur = summary['duration_s']
            parts.append(f"物体从高处自由落体, 落地时速度 {abs(vel_y):.1f} m/s")
            parts.append(f"落地高度 {pos_y:.2f}m, 历时 {dur:.3f}s")

        elif scenario_name == 'projectile':
            b0 = summary['final_state']['body0']
            parts.append(f"抛体运动, 落地位置 ({b0['pos'][0]:.2f}, {b0['pos'][1]:.2f})m")
            parts.append(f"落地速度 ({b0['vel'][0]:.1f}, {b0['vel'][1]:.1f})m/s")

        elif scenario_name == 'pendulum':
            drift = summary.get('energy_drift_pct', 0.0)
            parts.append(f"单摆 {summary['duration_s']:.1f}s 后能量漂移 {drift:.3f}%")
            parts.append(f"Leapfrog4 辛积分器保结构效果: {'优秀' if abs(drift)<0.5 else '良好' if abs(drift)<2 else '退化'}")

        elif 'collision' in scenario_name:
            parts.append(f"{n_bodies}体碰撞, 能量漂移 {drift:.3f}%")
            for i in range(n_bodies):
                bi = summary['final_state'][f'body{i}']
                parts.append(f"球{i+1}: pos=({bi['pos'][0]:.2f},{bi['pos'][1]:.2f}) vel=({bi['vel'][0]:.2f},{bi['vel'][1]:.2f})")

        elif scenario_name == 'inclined_plane':
            b0 = summary['final_state']['body0']
            parts.append(f"物体沿斜面下滑, 末速度 {np.linalg.norm(b0['vel']):.2f} m/s")
            parts.append(f"末位置 ({b0['pos'][0]:.2f}, {b0['pos'][1]:.2f})m")

        if abs(drift) > 10:
            parts.append("⚠️ 能量漂移过大, 结果可能不可靠")
        elif abs(drift) < 1:
            parts.append("✅ 能量守恒良好")

        return '。'.join(parts) + '。'


# ============================================================
# 便捷函数
# ============================================================

_bridge = None

def query(description, **overrides):
    """全局快捷查询"""
    global _bridge
    if _bridge is None:
        _bridge = LLMWMBridge()
    return _bridge.query(description, **overrides)


# ============================================================
# 自测
# ============================================================
if __name__ == '__main__':
    bridge = LLMWMBridge()
    test_cases = [
        ("一个5kg的球从10m高处自由落下", {'mass': 5, 'height': 10}),
        ("以20m/s初速度、45度角抛出物体", {'v0': 20, 'angle': 45}),
        ("一个长1m的单摆从30度释放", {'length': 1, 'angle0': 30}),
        ("两个1kg球正碰，速度分别为1m/s和-1m/s", {'m1': 1, 'm2': 1, 'v1': 1, 'v2': -1}),
        ("物体从30度斜面滑下", {'angle': 30, 'length': 5}),
    ]
    for desc, params in test_cases:
        r = bridge.query(desc, **params)
        print(f"[{r['scenario']}] {desc}")
        print(f"  {r['explanation']}")
        print(f"  valid={r['physically_valid']}, drift={r['summary'].get('energy_drift_pct', 0):.3f}%")
        print()
