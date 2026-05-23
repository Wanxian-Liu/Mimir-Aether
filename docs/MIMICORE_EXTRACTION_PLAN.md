# Mimicore 提炼方案

> **作者**：MimirAether（自主分析）  
> **日期**：2026-05-21  
> **状态**：Phase 1-2 可直接执行；Phase 3 需 Cursor 评估 Bridge §3 后启动  
> **Backlog**：`docs/MIMIR_EXEC_BACKLOG.md` §2n EV-MC01~MC10

---

## 1. 核心洞察

Mimicore（`mimicore/`，45,000 行，132 个 Python 文件，27 个子目录）和 MimirAether 的关系：

```
┌──────────────────────────────────┐
│         MimirAether              │
│  agent/  gateway/  tools/  ...   │
│                                  │
│  ┌────────────────────────┐      │
│  │      Mimicore           │      │
│  │  ┌──────────┐          │      │
│  │  │ L1 核心  │ 3,500行  │ ← 只有这 3,500 行被 Mimir 调用
│  │  │ L2 脚本  │ 脚本引用  │ ← 离线脚本层
│  │  │ L3 独立  │ 42,000行  │ ← Mimir 从未调用
│  │  └──────────┘          │      │
│  └────────────────────────┘      │
└──────────────────────────────────┘
```

**唯一管道**：`tools/mimircore_tool.py` 中的 `produce_capsule()` 函数。

**结论**：Mimicore 不是 Mimir 的"核心引擎"——它是两栋挨着的楼，共享一个 git 仓库。提炼完全可行。

---

## 2. 三层分析

### 🔵 L1 — Mimir 运行时真正在用的（~3,500 行）

| 模块 | 行数 | 功能 | Mimir 调用方 |
|------|:--:|------|-------------|
| `capsule_generator.py` | 911 | 知识→胶囊（三类） | `tools/mimircore_tool.py` → `produce_capsule` |
| `gdi_scorer.py` | 453 | GDI 四维评分 | CapsuleGenerator 内部依赖 |
| `evomap_validator.py` | 674 | 胶囊进化图验证 | CapsuleGenerator 内部依赖 |
| `gene_mapper.py` | 325 | 知识→基因类型 | CapsuleGenerator 内部依赖 |
| `evolve/three_ring_architecture.py` | 1083 | 监控→决策→执行→验证 | `skills/.../self_evolution/__init__.py` |
| `config/model_defaults.py` | 50 | LLM 模型解析 | `cli.py` / `api_service.py` |
| `config/loader.py` | ~100 | 配置加载 | `acp_adapter/session.py` |

**合计**：~3,500 行（占 Mimicore 总代码的 8%）

### 🟡 L2 — Mimir 离线脚本在用的

| 脚本 | 用 Mimicore 的什么 |
|------|-------------------|
| `run_capsule_*.py`（4个） | CapsuleGenerator |
| `scripts/diag_capsule.py` | CapsuleGenerator |
| `scripts/gen_and_score.py` | CapsuleGenerator |
| `scripts/eval_capsule_gdi.py` | CapsuleGenerator |
| `scripts/step3_append_generate_and_evaluate.py` | CapsuleGenerator |
| `activate_self_evolution.py` | ThreeRingClosedLoop |

运行时不影响——脚本层 import 路径可统一更新。

### ⚫ L3 — Mimicore 自己的独立系统（~42,000 行，Mimir 从未调用）

| 目录 | 文件数 | 是什么 |
|------|:--:|------|
| `introspection/` | 18 | 依赖图、问题检测/定位/分类、告警管理、状态 API |
| `health/` | 10 | 健康检查器、熔断器、诊断、指标面板 |
| `evolve/` | 5（除 three_ring） | diversity_executor / feedback / monitor_collector / self_evolution |
| `mini_agent/` | 5 | 独立微型 Agent 框架 |
| `agent/` | 6 | Mimicore 自己的 Agent（非 Mimir 的 agent/） |
| `gateway/` | 2 | Mimicore 自己的 Gateway（非 Mimir 的 gateway/） |
| `interfaces/` | 6 | 内存库接口、适配器 |
| `tests/` | 23 | Mimicore 自己的测试（非 tier0） |
| `cli/` | 4 | Mimicore 自己的 CLI |
| `classifier/` | 3 | 分类器 |
| `extractor/` | 3 | 提取器 |
| `normalizer/` | 2 | 标准化器 |
| `deduplication/` | 1 | 去重 |
| `fence/` | 2 | 护栏 |
| `pipeline/` | 2 | 管道 |
| `plugin/` | 3 | 插件系统 |
| `permission/` | 3 | 权限 |
| `repair/` | 2 | 修复 |
| `optimize/` | 2 | 优化 |
| `sensory/` | 3 | 感官 |
| `task/` | 2 | 任务 |
| `base_wal/` | 2 | WAL 基础层 |
| `utils/` | 2 | 工具函数 |
| `integrate/` | 4 | 集成层 |
| `audit/` | 2 | 审计 |

---

## 3. 提炼方案

### 产物 A：`mimiraether-capsule-factory` 技能

**移入文件**：

| 源路径 | 目标路径 |
|--------|---------|
| `mimicore/capsule_generator.py` | `skills/mimiraether/mimiraether-capsule-factory/capsule_generator.py` |
| `mimicore/gdi_scorer.py` | `skills/mimiraether/mimiraether-capsule-factory/gdi_scorer.py` |
| `mimicore/evomap_validator.py` | `skills/mimiraether/mimiraether-capsule-factory/evomap_validator.py` |
| `mimicore/gene_mapper.py` | `skills/mimiraether/mimiraether-capsule-factory/gene_mapper.py` |
| 新建 | `skills/mimiraether/mimiraether-capsule-factory/SKILL.md` |
| 新建 | `skills/mimiraether/mimiraether-capsule-factory/__init__.py` |

**需改动文件**：

| 文件 | 改动 |
|------|------|
| `tools/mimircore_tool.py` | 改 import：`from mimicore.capsule_generator` → `from skills.mimiraether.mimiraether-capsule-factory.capsule_generator` |
| 各离线脚本（`run_capsule_*.py` 等 6 个） | 同上改 import |

**外部依赖**：`pyyaml`（已在 Mimir 依赖中）、`hashlib`（stdlib）— 零新依赖。

### 产物 B：强化 `mimiraether-self_evolution` 技能

**移入文件**：

| 源路径 | 目标路径 |
|--------|---------|
| `mimicore/evolve/three_ring_architecture.py` | `skills/mimiraether/mimiraether-self_evolution/three_ring_architecture.py` |

**需改动文件**：

| 文件 | 改动 |
|------|------|
| `skills/mimiraether/mimiraether-self_evolution/__init__.py` | 改 import：`from mimicore.evolve.three_ring_architecture` → `from .three_ring_architecture` |
| `activate_self_evolution.py` | 同上改 import |

**关键事实**：`__init__.py` 目前 134 行，仅 import `ThreeRingClosedLoop` 一个类。three_ring_architecture.py 的 1083 行中，self_evolution 技能实际只用到了 ~300 行（`ThreeRingClosedLoop` 类及其 `run_cycle()` 方法）。

### 产物 C：模型配置内联

| 源 | 目标 |
|----|------|
| `mimicore/config/model_defaults.py`（50 行） | 逻辑内联到 `cli.py` + `api_service.py` |
| `mimicore/config/loader.py`（~100 行） | 逻辑内联到 `acp_adapter/session.py` |

**需改动文件**：3 个（`cli.py` / `api_service.py` / `acp_adapter/session.py`）

### 保留为离线参考（不改动）

```
mimicore/
├── L3 全部 22 个目录（42,000 行）    ← 保留不动
├── evolve/（除 three_ring_architecture.py）
└── config/llm_config.yaml              ← 保留（运行时仍读取）
```

---

## 4. 提炼后的架构

```
提炼前：
┌──────────────┐
│  MimirAether  │
│  ┌──────────┐ │
│  │ Mimicore │ │  ← 45K 行全嵌在进程里
│  │ 45K 行   │ │
│  └──────────┘ │
└──────────────┘

提炼后：
┌──────────────┐     ┌─────────────────────┐
│  MimirAether  │     │  mimicore/（参考）   │
│              │     │  42,000 行           │
│  skills/     │     │  离线保留            │
│  ├─ capsule  │     └─────────────────────┘
│  │  factory  │ ← 2,400 行
│  ├─ self     │
│  │  evolution│ ← 1,100 行
│  │           │
│  cli.py      │ ← 50 行内联
└──────────────┘
```

**收益**：
- Mimir 进程不再加载 42,000 行无用代码
- 胶囊生成和自进化成为标准技能（可独立安装/更新/卸载）
- Mimicore 参考代码保留在仓库，不影响 git 历史
- 每一步可回滚

---

## 5. 回滚策略

| 步骤 | 回滚命令 |
|------|---------|
| EV-MC07（移入胶囊工厂） | `git checkout mimicore/capsule_generator.py mimicore/gdi_scorer.py mimicore/evomap_validator.py mimicore/gene_mapper.py tools/mimircore_tool.py && rm -rf skills/mimiraether/mimiraether-capsule-factory` |
| EV-MC08（移入三环） | `git checkout mimicore/evolve/three_ring_architecture.py skills/mimiraether/mimiraether-self_evolution/__init__.py` |
| EV-MC09（内联配置） | `git checkout cli.py api_service.py acp_adapter/session.py mimicore/config/model_defaults.py mimicore/config/loader.py` |
| EV-MC10（验证） | tier0 回归确认基线不变 |

---

## 6. 风险

| 风险 | 等级 | 缓解 |
|------|:--:|------|
| capsule_generator 内部依赖 Mimicore 其他模块 | 低 | EV-MC03 会全映射，发现隐藏依赖则调整边界 |
| import 路径变更导致离线脚本中断 | 低 | 离线脚本非运行时，逐个更新即可 |
| three_ring_architecture 依赖 Mimicore 的 dataclass 定义 | 低 | EV-MC04 会标注，需要时将依赖类一并移入技能 |
| Mimicore L3 目录中有隐藏的 Mimir 引用 | 极低 | EV-MC02 会 grep 全仓确认 |

---

## 7. 执行顺序

```
EV-MC01 (import 审计) ────┐
EV-MC02 (L2 零触碰)  ────┤ Phase 1: 摸清现状
EV-MC03 (胶囊内部)   ────┤ 零风险只读
EV-MC04 (三环使用面) ────┘
        │
        ▼
EV-MC05 (提取设计) ────┐
EV-MC06 (回滚方案) ────┘ Phase 2: 精确设计
        │                   零风险只读
        ▼
      等 Cursor 判定 Bridge §3
        │
        ▼
EV-MC07 (胶囊工厂) ────┐
EV-MC08 (自进化)    ────┤ Phase 3: 执行
EV-MC09 (配置内联)  ────┤ 需 Cursor 解禁
EV-MC10 (tier0 验证) ───┘
```

---

## 8. 与三方案的关系

| 方案 | Mimicore 提炼如何贡献 |
|------|---------------------|
| **工程方案**（测试/GOD/去重） | 减少 42,000 行无效代码 = GOD 文件清单缩短 + 测试范围缩小 |
| **架构方案**（Core/Mimicore/Memory） | 直接完成架构方案方向二（Mimicore 服务化解耦）的 80%——提炼比服务化更彻底 |
| **智商方案**（学习/Prompt/记忆） | 胶囊工厂技能独立后，智商方案中的"经验学习"可直接调用胶囊管线 |

提炼是三个方案的**共同前置项**——先拆掉两栋楼之间的脚手架，工程/架构/智商才能各自独立推进。
