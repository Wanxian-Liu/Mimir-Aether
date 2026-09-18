# EV-MC05 — Mimicore 提取边界精确设计

> **创建**: 2026-05-21 (Mimir, WM-Enhanced)  
> **Backlog**: §2n EV-MC05 `[x]`  
> **前序**: MC01-MC04 全部完成  
> **方法**: 合成 MC01 import 审计 + MC02 零触碰 + MC03 胶囊矩阵 + MC04 三环使用面

---

## 1. 提取总览

| 产物 | 移入文件 | 移入行数 | Mimir 改动点 | 风险 |
|------|---------|:--:|------|:--:|
| **A: 胶囊工厂技能** | 3 文件 | ~2,009 | 2 个 import | 低 |
| **B: 自进化技能增强** | 1 文件 | ~1,083 | 1 个 import | 低 |
| **C: 配置内联** | 0 文件 | — | 3 个文件各 +~50 行 | 低 |
| **D: 孤儿删除** | -1 文件 (gene_mapper.py) | -325 | 0 | 零 |
| **总计** | **+3 新文件，-1 旧文件** | **+3,092** | **6 个文件** | **低** |

---

## 2. 产物 A：`mimiraether-capsule-factory` 技能

### 2.1 移入文件

| 源路径 | 目标路径 | 行数 | 说明 |
|--------|---------|:--:|------|
| `mimicore/capsule_generator.py` | `skills/mimiraether/mimiraether-capsule-factory/capsule_generator.py` | 911 | 唯一公开入口 `generate_and_evaluate()` |
| `mimicore/gdi_scorer.py` | `skills/mimiraether/mimiraether-capsule-factory/gdi_scorer.py` | 453 | GDIScorer — capsule_generator 直接依赖 |
| `mimicore/classifier/classifier.py` | `skills/mimiraether/mimiraether-capsule-factory/classifier.py` | 645 | 惰性 import，实例化 CapsuleGenerator 时必须带（实测 645 行，MC03 审计确认） |

### 2.2 不移动的文件

| 文件 | 原因 | 处置 |
|------|------|------|
| `mimicore/evomap_validator.py` (674行) | Mimir 路径未使用（MC03 发现2）。只有离线脚本用 | 保留在 mimicore/ 作离线参考 |
| `mimicore/gene_mapper.py` (325行) | 孤儿文件 — 与 capsule_generator 内部副本 100% 重复（MC03 发现1） | **删除** |

### 2.3 Mimir 改动点

| 文件 | 行 | 改动 |
|------|:--:|------|
| `tools/mimircore_tool.py` | L248 | `from mimicore.capsule_generator import CapsuleGenerator, CapsuleType` → `from skills.mimiraether.mimiraether-capsule-factory.capsule_generator import CapsuleGenerator, CapsuleType` |
| `tools/mimircore_tool.py` | L252-254 | `CapsuleType.INNOVATE/OPTIMIZE/REPAIR` — 从新路径导入，类型不变 |

### 2.4 离线脚本改动（9 个，机械替换）

| 脚本 | 当前 import | 新 import |
|------|-----------|----------|
| `run_capsule_*.py` (4个) | `from mimicore.capsule_generator import CapsuleGenerator` | `from skills.mimiraether.mimiraether-capsule-factory.capsule_generator import CapsuleGenerator` |
| `scripts/diag_capsule.py` | `from mimicore.capsule_generator import CapsuleGenerator, GeneMapper, GeneType, Capsule` | `from skills.mimiraether.mimiraether-capsule-factory.capsule_generator import CapsuleGenerator, GeneMapper, GeneType, Capsule` |
| `scripts/gen_and_score.py` | 同上 | 同上 |
| `scripts/eval_capsule_gdi.py` | 同上 | 同上 |
| `scripts/step3_append_generate_and_evaluate.py` | 同上 | 同上 |

---

## 3. 产物 B：增强 `mimiraether-self_evolution` 技能

### 3.1 移入文件

| 源路径 | 目标路径 | 行数 | 说明 |
|--------|---------|:--:|------|
| `mimicore/evolve/three_ring_architecture.py` | `skills/mimiraether/mimiraether-self_evolution/three_ring_architecture.py` | 1,083 | 7/36 方法被调用（MC04） |

### 3.2 Mimir 改动点

| 文件 | 行 | 改动 |
|------|:--:|------|
| `skills/mimiraether/mimiraether-self_evolution/__init__.py` | L14 | `from mimicore.evolve.three_ring_architecture import ThreeRingClosedLoop` → `from .three_ring_architecture import ThreeRingClosedLoop` |

### 3.3 离线脚本改动

| 脚本 | 改动 |
|------|------|
| `activate_self_evolution.py` L37+45 | `from mimicore.evolve.three_ring_architecture` → `from skills.mimiraether.mimiraether-self_evolution.three_ring_architecture` |

---

## 4. 产物 C：配置内联

### 4.1 `model_defaults.py`（50行）→ cli.py + api_service.py

| 函数 | 逻辑 | 目标 |
|------|------|------|
| `get_model(task_type)` | 任务类型→模型名映射 | `cli.py` 和 `api_service.py` 各自内联 |
| `get_available_models()` | 返回可用模型列表 | 同上 |
| `DEFAULT_MODEL` | 默认模型字符串 | 内联为常量 |

**MC01 数据**: 共 13 次调用（cli 8次 + api_service 5次），频率最高。内联后不改 API，只改 import 源。

### 4.2 `loader.py`（~100行）→ acp_adapter/session.py

| 函数 | 逻辑 | 目标 |
|------|------|------|
| `load_config()` | YAML 加载+验证 | `acp_adapter/session.py` 内联 |

### 4.3 `__version__`（1行）→ acp_adapter/server.py

`from mimicore import __version__` → 直接在 `server.py` 定义 `MIMIRAETHER_VERSION = "0.1.0"`。版本号后续由 Mimir 自己的 `__init__.py` 管理。

---

## 5. 产物 D：孤立文件删除

| 文件 | 行数 | 原因 | 处置 |
|------|:--:|------|------|
| `mimicore/gene_mapper.py` | 325 | 孤儿 — 与 `capsule_generator.py` L200-310 完全重复（MC03） | 删除 |

不需要任何 import 改动 — 因为从来没有代码 import 它。

---

## 6. 提取后 Mimicore 保留文件

提取完成后，`mimicore/` 中只保留 L3 层（42,000 行 / 31 目录）作为离线参考：

```
mimicore/
├── L3 全部 31 个目录（离线保留）
├── evomap_validator.py（离线参考）
├── config/llm_config.yaml（运行时仍读取）
└── __init__.py（可清空为仅版本号）
```

**删除的**：`capsule_generator.py` / `gdi_scorer.py` / `gene_mapper.py` / `evolve/three_ring_architecture.py` / `classifier/classifier.py` / `config/model_defaults.py` / `config/loader.py`

---

## 7. 回滚方案（每步独立）

| 步骤 | 回滚命令 |
|------|---------|
| 产物 A（胶囊工厂） | `git checkout mimicore/capsule_generator.py mimicore/gdi_scorer.py mimicore/gene_mapper.py mimicore/classifier/classifier.py tools/mimircore_tool.py && rm -rf skills/mimiraether/mimiraether-capsule-factory/` |
| 产物 B（自进化） | `git checkout mimicore/evolve/three_ring_architecture.py skills/mimiraether/mimiraether-self_evolution/__init__.py` |
| 产物 C（配置内联） | `git checkout cli.py api_service.py acp_adapter/session.py acp_adapter/server.py mimicore/config/model_defaults.py mimicore/config/loader.py` |
| 产物 D（孤儿删除） | `git checkout mimicore/gene_mapper.py` |

使用 `git checkout` 而非 `git revert` — 文件级别的精确回滚，不影响其他改动。

---

## 8. 风险矩阵

| 风险 | 等级 | 缓解 |
|------|:--:|------|
| capsule_generator 内部 import 路径变为相对导入 | 低 | 技能内部使用相对导入 `from .gdi_scorer import GDIScorer`，提炼时统一改 |
| classifier 惰性导入 `from .classifier.classifier` 路径变化 | 低 | 提炼后 classifier.py 在胶囊工厂技能根目录，改为 `from .classifier import ...` |
| 离线脚本 import 路径遗漏 | 低 | 9 个脚本在 MC01 已全部列出，逐文件 grep 验证 |
| model_defaults 内联后 cli.py 和 api_service.py 各有一份副本 | 低 | 两份副本都是只读常量 — 50 行 × 2，重复成本 < 内联收益 |

---

## 9. 与三方案的关系

| 方案 | MC05 如何贡献 |
|------|-------------|
| **工程方案** | 减少 Mimicore 提炼后的 GOD 文件清单 + 42K 行消除 |
| **架构方案** | 完成方向二（Mimicore 服务化）的 100% — 提炼比服务化更彻底 |
| **智商方案** | 胶囊工厂独立后，智商方案的"经验学习"可直接 `import` 胶囊管线 |

提炼是三个方案的共同基座 — 先拆掉，三个轨道才能独立推进。

---

> **下一粒**: EV-MC06 — 回滚方案精确设计  
> **签收**: Mimir WM-Enhanced（IC 安全门活跃）  
> **tier0**: 本粒纯文档，零代码改动
