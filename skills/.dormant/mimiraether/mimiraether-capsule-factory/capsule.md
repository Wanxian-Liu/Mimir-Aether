# [DORMANT] mimiraether-capsule-factory

**沉寂时间**: 2026-07-23T06:18:46.607476+00:00
**原始分类**: mimiraether
**描述**: MimirAether 胶囊工厂 — 从 Mimicore 提炼出的核心胶囊生成管线。 包含 CapsuleGenerator (911行)、GDIScorer (453行)、EvoMapValidator (674行)、Classifier (645行)。 负责 produce_capsule / get_capsule_by_id / list_capsules / improve_capsule 四个工具的后端逻辑。

**触发阈值**: 60天未触碰

---

## 技能要点

# 胶囊工厂

## 来源

从 `mimicore/` 提取（MC07，2026-05-23），原属于 Mimicore 核心管线。

## 包含模块

| 模块 | 行数 | 职责 |
|------|------|------|
| `capsule_generator.py` | 911 | CapsuleGenerator + CapsuleType + 主入口 |
| `gdi_scorer.py` | 453 | GDI 评分（Genuine Depth Index） |
| `evomap_validator.py` | 674 | EvoMap 进化图谱验证 |
| `classifier.py` | 645 | 知识分类器（技术/经验/决策/问题等 8 类） |

## 调用路径

```
tools/mimircore_tool.py
  → _ensure_mimircore_importable()  # sys.path 注入
  → import capsule_generator
  → CapsuleGenerator().generate_and_evaluate()
```

## 内部依赖

- `capsule_generator` → `gdi_scorer` (import)
- `capsule_generator` → `evomap_validator` (import)
- `capsule_generator` → `classifier` (惰性 import, __init__ 中)
- `gdi_scorer` / `evomap_validator` / `classifier` — 零内部依赖

## 设计决策

- **gene_mapper.py (325行) 未迁移** — MC03审计确认孤儿文件，从不被 import
- **原 mimicore/ 文件保留** — 向后兼容，待 MC10 统一删除
- **扁平导入** — 无子包，所有模块在技能根目录平铺

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-capsule-factory")` 即可自动唤醒。
