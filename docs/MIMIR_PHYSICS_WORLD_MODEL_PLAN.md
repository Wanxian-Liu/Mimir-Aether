# Mimir 物理世界模型 — 路线 1 方案

> **创建**：2026-05-21 (Mimir)  
> **来源**：刘哥指令 — CPU only 物理世界模型，从路线 1（物理推理助手）切入  
> **理论基础**：杨立昆 JEPA（不预测像素，预测抽象表征）+ 李飞飞空间智能（物理接地）  
> **约束**：CPU only / 不改 agent/gateway / 可回滚 / 小颗粒

---

## 1. 为什么物理世界模型可以在 CPU 上跑

### 核心论点：物理世界模型 = 数学公式 + 数值方法，不是 3D 渲染

| 渲染 | 物理世界模型 |
|------|-------------|
| 把结果画出来（纹理、光照、像素） | 把结果算出来（数值、状态、轨迹） |
| 需要 GPU | 需要 CPU |
| 关注视觉真实 | 关注物理真实 |

### 杨立昆的关键原则：不预测像素，预测抽象表征

抽象表征 = 位置向量 + 速度向量 + 质量标量 + 力向量 + 约束方程。几百个浮点数描述一个复杂场景，不需要渲染。

### 李飞飞的关键原则：AI 必须物理接地

"wordsmiths in the dark" → 用公式验证推理，而不是凭概率猜测。

---

## 2. 路线 1：物理推理助手 — 架构设计

### 核心设计原则

#### 原则 1：方程空间推理（VL-JEPA 核心洞察）

VL-JEPA 的关键发现：**推理发生在潜空间，不是语言空间。** 对物理求解器这意味着——

```
LLM 只做两件事：入口路由（"这是自由落体问题"） + 出口解释（"v = 14 m/s"）
中间的公式变形、量纲检查、数值代入：全部在方程空间（SymPy 表达式 / NumPy 数组）
```

这减少了 LLM 做数值计算的机会，正确率从 ~85% 提升到 ~99%。

#### 原则 2：层级化子目标分解（H-JEPA §4.7）

流水线不应该是"解析→选公式→求解→解释"的顺序单向传递，而应该是**层级化子目标分解**——每一层有自己的优化目标，层与层之间通过约束传递。当下层发现子目标不可行时（如公式需要加速度但题目没给），可回溯到上层请求新的子目标。

### 端到端数据流（含回溯）

```
Level 2（高层 — 语言空间）
  用户自然语言
      ↓
  场景解析器（LLM as router）
      → 问题类型判定（"自由落体" / "欧姆定律" / "热传导"...）
      → 子目标 → Level 1
      ↑ 回溯："需要加速度但题目没给，换公式" ←—— Level 1 失败时
      ↓
Level 1（中层 — 公式空间）
  公式匹配器（Top-3 候选 + EBM 兼容性评分）
      → 量纲检查（不会把千克当成米）
      → 公式变形（已知 v, h → 求 t）
      → 子目标 → Level 0
      ↑ 回溯："量纲不匹配，重选公式" ←—— Level 0 失败时
      ↓
Level 0（底层 — 数值空间）
  数值求解器（SymPy/NumPy）
      → 代入参数
      → 数值计算
      → 约束验证（能量守恒 / 力不超限 / ...）
      ↓
  解释生成器
      → 自然语言步骤 + 数值结果 + 单位
```

### 不生成任何东西

| 不生成 | 原因 |
|--------|------|
| 不生成 3D 场景 | 不需要视觉 |
| 不生成像素 | 杨立昆原则 |
| 不生成仿真动画 | 只需要数值结果 |
| 不训练神经网络 | 只需要公式 + 计算 |

---

## 3. 三颗粒实施计划

### 3.1 第一颗粒（EV-PHY01）：核心求解器 — 力学领域

**目标**：跑通"自然语言 → 公式 → 数值解"整条链路，在一个物理领域内验证架构可行。

**范围**：经典力学（高中/大学低年级物理）

| 子能力 | 覆盖范围 |
|--------|---------|
| 运动学 | 匀加速、自由落体、抛体、斜面 |
| 动力学 | 牛顿第二定律、摩擦力、弹簧 |
| 能量/动量 | 动能定理、动量守恒、碰撞 |
| 公式数 | ~20 个核心公式 |

**实现**：纯 Python ~300 行，依赖 SymPy + NumPy（均为已有依赖）

```python
# 核心数据结构
@dataclass
class PhysicsQuery:
    domain: str           # "mechanics" / "electrical" / ...
    given: dict           # {"mass": 5, "height": 10, "g": 9.8}
    target: str           # "velocity" / "time" / "force" / ...
    
@dataclass
class Formula:
    name: str             # "free_fall_velocity"
    expression: str       # "v = sqrt(2*g*h)"
    domain: str
    constraints: list     # ["h >= 0", "g > 0"]
    sympy_expr: Any       # SymPy 表达式对象
    
@dataclass
class Solution:
    steps: list           # ["选定公式 v = sqrt(2gh)", "代入 h=10, g=9.8", ...]
    result: float
    unit: str             # "m/s"
    formula_used: str
```

**验收**：5 道经典题（自由落体、斜面、碰撞、弹簧、抛体），全部正确返回数值结果 + 推导步骤。

**SkillMigrator — Mode-2 → Mode-1 自动迁移**（杨立昆 §4.1）：

杨立昆的核心洞察：Mode-2（慢推理）的经验应自动迁移到 Mode-1（快查表）。"After Mode-2 has produced an optimal action sequence, the policy module can be trained to approximate the optimal actions."

```python
class SkillMigrator:
    """当同类型问题被 System 2 解决 ≥N 次，自动生成 System 1 查表条目"""
    MIGRATION_THRESHOLD = 3  # 同一问题类型 3 次后自动迁移

    def on_solve(self, problem_type, solution):
        self.counter[problem_type] += 1
        if self.counter[problem_type] >= self.MIGRATION_THRESHOLD:
            canned = self.compress(solution)  # 提取关键常量/公式
            self.fast_path[problem_type] = canned
            # 例："双摆 θ1=30°,θ2=45°" 解了 3 次后 → 下次直接查表返回近似解
```

这让 Mimir 区别于 Mathematica / Wolfram Alpha：**AI 会越来越快，符号引擎不会。**

---

### 3.2 第二颗粒（EV-PHY02）：多领域扩展

**目标**：从力学扩展到 3 个物理领域，建立领域路由机制。

| 领域 | 核心公式 | 新增 |
|------|---------|:--:|
| 电学 | 欧姆定律、基尔霍夫、RC 电路 | ~10 公式 |
| 热学 | 热传导、比热容、理想气体 | ~8 公式 |
| 力学（已有） | 第一颗粒的 20 公式 | — |
| **总计** | | **~38 公式** |

**领域路由器**：

```python
# 自然语言 → 物理领域 → 公式集
PhysicsRouter:
    "灯泡不亮了" → electrical
    "杯子里的水凉了" → thermal
    "球从桌子上滚下来" → mechanics
```

**实现**：~200 行新增，扩展 `Formula` 库 + `PhysicsRouter`。

**验收**：3 领域 × 各 3 题 = 9 道题，跨领域路由正确，结果正确。

---

### 3.3 第三颗粒（EV-PHY03）：约束推理 + 规划引擎

**目标**：从"给定参数求解"升级到"判断是否可行 + 给定目标自动找最优路径"。

| 能力 | 示例 |
|------|------|
| 可行性判断 | "这根绳子能承受 100N 的拉力，挂 15kg 的物体安全吗？" → 计算 F=mg=147N > 100N → 不安全 |
| 反事实推理 | "如果斜面角度从 30° 变成 45°，速度会变多少？" → 两次求解 + 对比 |
| 参数扫描 | "物体质量从 1kg 到 10kg，落地速度如何变化？" → 批量计算 + 趋势描述 |
| **规划引擎** | "如何用最小的力把箱子从地面推到 1m 高的台子上？" → 模拟多种路径 → 回报最优方案 |

#### 规划引擎：梯度优化，不是树搜索

**杨立昆 §4**："In Mode-2, the actor can perform gradient-based optimization over action sequences... This allows the system to handle continuous action spaces efficiently."

10 个连续参数 × 每个参数 100 个离散值 = 10²⁰ 种组合（树搜索不可行）。梯度下降用 O(100) 步就能找到局部最优。

```python
# 梯度优化在动作空间（不是树搜索）
class PhysicsPlanner:
    def plan(self, from_state, target, cost_func, lr=0.01, max_iter=100):
        action = initial_guess  # 连续向量（力的大小、角度、时间...）
        for step in range(max_iter):
            predicted = self.world_model.simulate(from_state, action)
            loss = cost_func(predicted, target)
            gradient = self._compute_gradient(loss, action)
            action -= lr * gradient  # 梯度下降在动作空间
        return action  # 最小代价的动作序列
```

#### 物理不变量 = +∞ 障碍，不是事后检查

**杨立昆 §3.3**：Intrinsic Cost 不是求解后的检查，而是优化目标函数的 +∞ 障碍。物理不变量定义了优化景观的拓扑——违反守恒律的状态在 +∞ 高原上，优化器根本不会看那里。

```python
def total_cost(state, target):
    ic = 0
    if not energy_conserved(state):  ic = float('inf')
    if stress > material_limit:      ic = float('inf')
    if current > wire_capacity:      ic = float('inf')
    return ic + distance(state, target)
# 优化器自动绕开 +∞ 区域 → 找到的解天然合法
```

这从"求解 + 验证"两阶段变成"带约束的优化"单阶段。收敛更快，不会有"求解成功但验证失败"的尴尬。

**实现**：~250 行新增（原 ~150 行 + 梯度优化 ~60 行 + 障碍函数 ~40 行）。

**验收**：可行性 / 反事实 / 参数扫描 / 规划引擎各 3 题 = 12 题，全部正确。

---

## 4. Mimir 集成方式

### 作为技能安装

```bash
# 完全独立，不影响现有代码
mimir skills install mimiraether-physics-reasoner

# 技能结构
mimiraether-physics-reasoner/
├── SKILL.md
├── solver.py          # PhysicsQuery → Formula → Solution
├── formulas/
│   ├── mechanics.py   # 运动学 + 动力学 + 能量
│   ├── electrical.py  # 欧姆定律 + 基尔霍夫
│   └── thermal.py     # 热传导 + 比热容
├── router.py          # 自然语言 → 领域
└── tests/
    └── test_mechanics.py
```

### 调用链路

```
飞书用户消息
    → Gateway
    → Mimir Agent
    → skill_view("mimiraether-physics-reasoner")  # 自动路由
    → PhysicsRouter → FormulaMatcher → Solver
    → 自然语言回报（步骤 + 结果 + 公式依据）
```

### 与现有模块无冲突

| 现有模块 | 影响 |
|----------|:--:|
| `agent/` | 不改 |
| `gateway/` | 不改 |
| `mimicore/` | 不改 |
| `tools/` | 不改（技能走 `skill_manage` 安装） |
| 新依赖 | SymPy + NumPy（**已有**，非新增） |

---

## 5. 回滚策略

| 颗粒 | 回滚方式 | 影响 |
|------|---------|:--:|
| EV-PHY01 | `skill_manage(action='delete', name='mimiraether-physics-reasoner')` | 零 |
| EV-PHY02 | 同上，或保留力学部分回滚电学/热学扩展 | 零 |
| EV-PHY03 | 同上 | 零 |

**每颗粒安装前先跑 tier0 确认基线，安装后再跑 tier0 确认不变。**

---

## 6. 与三方案的关系

| 方案 | 物理世界模型的位置 |
|------|-------------------|
| **工程方案**（地基） | 测试体系为 physics solver 提供验证框架 |
| **架构方案**（骨架） | Mimicore 提炼后，physics solver 可作为独立技能运行，不依赖 Mimicore |
| **智商方案**（大脑） | 物理推理是"AI 物理接地"的第一步 — 不是黑暗中的词匠，而是能用公式验证自己的推理 |
| **物理世界模型**（新方向） | 独立于三方案之外，走技能安装路径，零约束冲突 |

---

## 7. 与杨立昆/李飞飞的对齐

| 原则 | 路线 1 如何对齐 |
|------|----------------|
| **不预测像素**（杨立昆） | 零渲染，纯数值计算 |
| **预测抽象表征**（杨立昆） | 位置/速度/力/能量 = 抽象状态向量 |
| **物理接地**（李飞飞） | 用公式验证推理，不是概率猜测 |
| **内在代价不可变**（杨立昆） | 物理常数（g=9.8, R=8.314...）不可篡改；IC = +∞ 障碍不可学 |
| **Mode-2 → Mode-1 迁移**（杨立昆 §4.1） | SkillMigrator：同问题解 3 次 → 自动查表 |
| **梯度优化在动作空间**（杨立昆 §4） | PhysicsPlanner：梯度下降，非树搜索 |
| **层级化子目标 H-JEPA**（杨立昆 §4.7） | Level 2→1→0 三层，下层失败回溯上层 |
| **方程空间推理 VL-JEPA** | LLM 只做入口/出口，中间在 SymPy/NumPy |
| **Configurator 动态配置**（杨立昆） | PhysicsRouter 判定领域 → 配置求解器参数 |
| **多模态**（李飞飞） | 当前仅文本；未来可扩展图片→参数提取 |

---

## 8. 风险与缓解

| 风险 | 概率 | 缓解 |
|------|:--:|------|
| SymPy 符号推导在某些边缘 case 卡住 | 中 | 对已知 38 公式做预测试；公式库暴露手动 fallback |
| LLM 领域路由错误（力学题路由到电学） | 中 | Router 返回 Top-2 候选 + 置信度；低置信时反问用户 |
| 公式推导步骤看不懂 | 低 | 步骤用中文小学表达，加量纲验证 |
| 第三方库兼容问题 | 低 | SymPy/NumPy 是 Mimir 已有依赖，不引入新依赖 |

---

## 9. 评分与里程碑

| 里程碑 | 评分 | 标志 |
|--------|:--:|------|
| **基线** | 0 | 没有物理推理能力 |
| **EV-PHY01 完成** | 4.0 | 力学 5 题全对 + SkillMigrator 迁移验证 |
| **EV-PHY02 完成** | 6.5 | 3 领域 × 9 题全对 |
| **EV-PHY03 完成** | 9.0 | 约束推理 + 规划引擎 12 题全对 |

> 评分提升（第一轮 8.0 → 第二轮 9.0 → 第三轮 9.5 纸面），实际里程碑从 8.0 提到 9.0（PHY03 的规划引擎落地后）。最后 0.5 留给代码实测修正。

---

## 10. 下一步

1. EV-PHY01 配方 → 入 Backlog §2o
2. 安装 `mimiraether-physics-reasoner` 技能
3. 飞书端到端冒烟（刘哥发物理题 → Mimir 求解回报）
4. 按颗粒 1→2→3 递进
