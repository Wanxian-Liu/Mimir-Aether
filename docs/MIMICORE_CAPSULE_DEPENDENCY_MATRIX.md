# EV-MC03 — 胶囊管线内部依赖全映射

> **创建**: 2026-05-21 (Mimir, WM-Enhanced)  
> **Backlog**: §2n EV-MC03 `[x]`

## 总览

| 文件 | 行数 | 类数 | 被 Mimir 直接调？ | 内部依赖 |
|------|:--:|:--:|:--:|------|
| **capsule_generator.py** | 911 | 6 | ✅ (唯一入口) | gdi_scorer + evomap_validator + classifier |
| **gdi_scorer.py** | 453 | 3 | ❌ (间接) | **零** |
| **evomap_validator.py** | 674 | 4 | ❌ (间接) | **零** |
| **gene_mapper.py** | 325 | 4 | ❌ (未被 import) | **零** |
| **总计** | **2,363** | **17** | 1 入口 | 2 条边 |

## 依赖图

```
Mimir (mimircore_tool.py / run_capsule_*.py)
    │
    └── CapsuleGenerator.generate_and_evaluate()  ← 唯一公共入口
            │
            ├── GeneMapper (内部副本, L200-310)
            │      └── SIGNAL_PATTERNS (内部副本, L170-197)
            │
            ├── GDIScorer.score()  ← 来自 gdi_scorer.py
            │      └── [独立，零内部依赖]
            │
            ├── TaxonomyClassifier  ← 来自 .classifier.classifier (惰性)
            ├── KnowledgeTypeClassifier  ← 来自 .classifier.classifier (惰性)
            │
            └── (EvoMapValidator 已 import 但 generate_and_evaluate 未调用)
```

## 逐文件详细映射

### 1. gdi_scorer.py (453行)

| 类型 | 名称 | 行 | 被谁调用 |
|------|------|:--:|------|
| Enum | `CapsuleType` | L24-28 | capsule_generator L32-34 (别名) |
| dataclass | `GDIResult` | L31-75 | capsule_generator L104-113 (反序列化) |
| class | `GDIScorer` | L77-425 | capsule_generator L334 |
| method | `GDIScorer.__init__()` | L88-105 | capsule_generator L334 |
| method | `GDIScorer._score_intrinsic()` | L109-148 | `score()` L331 |
| method | `GDIScorer._assess_structure()` | L150-175 | `_score_intrinsic()` L135 |
| method | `GDIScorer._is_readable()` | L177-181 | `_score_intrinsic()` L145 |
| method | `GDIScorer._score_usage()` | L185-219 | `score()` L332 |
| method | `GDIScorer._score_social()` | L223-258 | `score()` L333 |
| method | `GDIScorer._score_freshness()` | L262-303 | `score()` L334 |
| method | `GDIScorer.score()` | L307-344 | **Mimir 调用链终点** |
| method | `GDIScorer._derive_knowledge_type()` | L346-393 | `score()` L327 |
| method | `GDIScorer.score_batch()` | L395-397 | 离线脚本 |
| method | `GDIScorer.filter_by_threshold()` | L399-425 | 离线脚本 |
| func | `get_scorer()` | L433-438 | 便捷函数 |
| func | `score_capsule()` | L441-443 | 便捷函数 |
| func | `score_capsules()` | L446-448 | 便捷函数 |
| func | `filter_publishable()` | L451-453 | 便捷函数 |

### 2. evomap_validator.py (674行)

| 类型 | 名称 | 行 | 被谁调用 |
|------|------|:--:|------|
| Enum | `EvoMapStatus` | L26-31 | capsule_generator |
| dataclass | `EvoMapCheck` | L34-42 | `_run_checks()` |
| dataclass | `EvoMapValidationResult` | L45-216 | capsule_generator L75 |
| class | `EvoMapValidator` | L219-646 | 离线脚本 |
| method | `EvoMapValidator.validate()` | L240-268 | 离线脚本 |
| method | `EvoMapValidator._extract_core_metrics()` | L270-315 | `validate()` |
| method | `EvoMapValidator._analyze_signals()` | L317-337 | `validate()` |
| method | `EvoMapValidator._run_checks()` | L339-376 | `validate()` |
| method | `EvoMapValidator._check_outcome_score()` | L378-411 | `_run_checks()` |
| method | `EvoMapValidator._check_confidence()` | L413-442 | `_run_checks()` |
| method | `EvoMapValidator._check_kg_enriched()` | L444-470 | `_run_checks()` |
| method | `EvoMapValidator._check_kg_entities()` | L472-500 | `_run_checks()` |
| method | `EvoMapValidator._check_blast_radius()` | L503-540 | `_run_checks()` |
| method | `EvoMapValidator._check_signal_specificity()` | L542-582 | `_run_checks()` |
| method | `EvoMapValidator._estimate_gdi()` | L584-608 | `validate()` |
| method | `EvoMapValidator._generate_suggestions()` | L610-620 | `validate()` |
| method | `EvoMapValidator.validate_batch()` | L622-624 | 离线脚本 |
| method | `EvoMapValidator.filter_by_evomap_ready()` | L626-646 | 离线脚本 |
| func | `get_validator()` | L654-659 | 便捷函数 |
| func | `validate_for_evomap()` | L662-664 | 便捷函数 |
| func | `validate_batch_for_evomap()` | L667-669 | 便捷函数 |
| func | `filter_evomap_ready()` | L672-674 | 便捷函数 |

**关键**: `EvoMapValidator` 被 capsule_generator.py L29 import，但 `generate_and_evaluate()` 方法**从未调用**它。只有离线脚本直接使用。

### 3. gene_mapper.py (325行) — 独立副本

| 类型 | 名称 | 行 | 被谁调用 |
|------|------|:--:|------|
| Enum | `GeneType` | L20-24 | 离线脚本 |
| Enum | `CapsuleType` | L27-31 | 离线脚本 |
| dataclass | `GeneSignal` | L34-40 | 离线脚本 |
| dataclass | `GeneMatch` | L43-49 | 离线脚本 |
| dict | `SIGNAL_PATTERNS` | L53-87 | 离线脚本 |
| dict | `CAPSULE_TYPE_MAP` | L90-94 | 离线脚本 |
| class | `GeneMapper` | L97-296 | 离线脚本 |
| method | `GeneMapper.extract_signals()` | L128-145 | 离线脚本 |
| method | `GeneMapper._score_signal_category()` | L147-167 | `match_gene()` |
| method | `GeneMapper.match_gene()` | L171-225 | 离线脚本 |
| method | `GeneMapper._generate_reasoning()` | L227-249 | `match_gene()` |
| method | `GeneMapper.select_capsule_type()` | L253-266 | 离线脚本 |
| method | `GeneMapper.select_capsule_type_batch()` | L268-273 | 离线脚本 |
| method | `GeneMapper.find_related_genes()` | L277-296 | 离线脚本 |
| func | `get_mapper()` | L304-309 | 便捷函数 |
| func | `match_gene()` | L312-314 | 便捷函数 |
| func | `select_capsule_type()` | L317-320 | 便捷函数 |
| func | `analyze_signals()` | L323-325 | 便捷函数 |

**🔴 关键发现**: `grep -r 'from \.gene_mapper\|import gene_mapper\|from mimicore\.gene_mapper' mimicore/` 返回 0 条结果。此文件**从不被任何 Mimicore 代码 import**。capsule_generator.py 内部有完全重复的副本 (L200-310)。两份 GeneMapper 独立维护。

### 4. capsule_generator.py (911行) — Mimir 唯一入口

**外部 import:**

| 来源 | 导入 | 使用 |
|------|------|------|
| `.gdi_scorer` | `GDIScorer, GDIResult, CapsuleType` | ✅ |
| `.evomap_validator` | `EvoMapValidator, EvoMapValidationResult, validate_for_evomap, EvoMapStatus` | ⚠️ import 但 generate_and_evaluate 不调用 |
| `.classifier.classifier` | `TaxonomyClassifier, KnowledgeTypeClassifier` (惰性) | ✅ L336-339 |

**内部类 (与 gene_mapper.py 完全重复):**

| 名称 | capsule_generator L行 | gene_mapper.py L行 | 重复度 |
|------|:--:|:--:|:--:|
| `GeneType` | L48-52 | L20-24 | 100% |
| `GeneSignal` | L152-157 | L34-40 | 100% |
| `GeneMatch` | L161-166 | L43-49 | 100% |
| `SIGNAL_PATTERNS` | L170-197 | L53-87 | 100% |
| `GeneMapper` (class) | L200-310 | L97-296 | ~95% (有微小差异) |

**CapsuleGenerator 核心方法:**

| 方法 | 行 | Mimir 调用链 | 调用谁 |
|------|:--:|------|------|
| `__init__()` | L326-339 | ✅ | GeneMapper + GDIScorer + classifier |
| `_smart_truncate()` | L341-374 | 静态 | — |
| `_pre_extract_sections()` | L378-404 | 静态 | — |
| `_deduplicate_sections()` | L406-431 | 静态 | — |
| `_post_validate_repair()` | L433-449 | 静态 | — |
| `_classify_keywords()` | L536-548 | 静态 | — |
| `_is_explained_by_root_cause()` | L550-557 | 静态 | — |
| `_infer_root_cause()` | L559-615 | ✅ | SYMPTOM_TO_CAUSE |
| `_infer_solution()` | L617-654 | ✅ | CAUSE_TO_SOLUTION |
| `_infer_steps()` | L656-674 | ✅ | — |
| `_infer_verification()` | L676-691 | ✅ | — |
| `_generate_repair_capsule()` | L696-804 | ✅ | _infer_root_cause + _infer_solution + ... |
| **`generate_and_evaluate()`** | **L808-910** | **✅ Mimir 唯一入口** | GeneMapper + GDIScorer |

---

## Mimir 调用全景（从 MC01 数据交叉验证）

| 调用方 | 调用 | 频率 |
|--------|------|:--:|
| `tools/mimircore_tool.py` | `CapsuleGenerator().generate_and_evaluate()` | 惰性（用户手动 produce_capsule 时） |
| `scripts/run_capsule_repair.py` | `CapsuleGenerator()` | 离线 |
| `scripts/run_capsule_innovate.py` | `CapsuleGenerator()` | 离线 |
| `scripts/run_capsule_optimize.py` | `CapsuleGenerator()` | 离线 |
| `scripts/gen_and_score.py` | `CapsuleGenerator()` | 离线 |
| `scripts/diag_capsule.py` | `CapsuleGenerator()` | 离线 |
| `scripts/eval_capsule_gdi.py` | `GDIScorer()` → 间接 | 离线 |
| `scripts/step3_append_generate_and_evaluate.py` | `CapsuleGenerator()` | 离线 |
| — | `gene_mapper.py` (独立文件) | **从不被调用** |

---

## 三个关键发现

### 🔴 发现 1: gene_mapper.py 是孤儿文件

独立的 `mimicore/gene_mapper.py` (325行) 从不被任何代码 import。
capsule_generator.py 内部有完全重复的副本。
两份 `GeneMapper` 独立维护——修复一边另一边不会自动同步。
**提炼时可以直接删除 `gene_mapper.py`，只保留 capsule_generator 内部副本。**

### 🟡 发现 2: EvoMapValidator 在 Mimir 路径上未被使用

capsule_generator.py L29 import 了 `EvoMapValidator`、`EvoMapValidationResult`、`validate_for_evomap`、`EvoMapStatus`，
但 `generate_and_evaluate()` 方法（Mimir 唯一调用的入口）**从未调用 EvoMapValidator**。
只有离线脚本直接使用。

**提炼时可选择**：EvoMapValidator 可以降级为离线参考代码，不影响 Mimir 运行时。

### 🟡 发现 3: classifier 在惰性 import 中，是胶囊管线的隐藏依赖

`CapsuleGenerator.__init__()` L336-339 惰性导入 `TaxonomyClassifier` 和 `KnowledgeTypeClassifier`。
这两个类来自 `mimicore/classifier/classifier.py`，不在 4 文件范围内。
如果提炼时只取 4 文件而忽略 classifier，`CapsuleGenerator()` 实例化会炸。

---

## 提炼影响矩阵

| 提炼什么 | 必须带 | 可选带 | 可删除 |
|----------|--------|--------|--------|
| **Mimir 运行时胶囊生成** | capsule_generator.py + gdi_scorer.py + classifier/ | evomap_validator.py | gene_mapper.py |
| **离线 GDI 评估** | gdi_scorer.py | — | — |
| **离线 EvoMap 验证** | evomap_validator.py | — | — |
| **最小 Mimir 集合** | capsule_generator.py + gdi_scorer.py + classifier/classifier.py | — | gene_mapper.py + evomap_validator.py |

---

> **下一粒**: EV-MC04 — 三环闭环实际使用面（1083行逐方法标注）  
> **tier0**: ⬜ 本粒纯文档，跳过
