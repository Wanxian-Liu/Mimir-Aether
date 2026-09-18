# docs/archive/mimicore — mimicore 域文档归档（tier: 归档·冻结）

**tier：** 归档文档（archived）· **冻结** · 不逐篇改写

本目录收纳 **mimicore 域**的历史设计/审计/提取文档（2026-05 ~ 2026-06 波次产出）。
mimicore 本体已于 2026-09-18 归档（纪念堂仪式：主体解绑 + tag `mimicore-archived-20260918`
+ 本体移至 `~/src/archive/mimicore-prototype/`），故其文档随之下沉到本目录。

| 文件 | 主题 |
|---|---|
| ARCHITECTURE_AUDIT_MIMICORE_DEPS.md | mimicore 依赖架构审计 |
| MIMICORE_CAPSULE_DEPENDENCY_MATRIX.md | 胶囊依赖矩阵 |
| MIMICORE_EXTRACTION_BOUNDARY_DESIGN.md | 提取边界设计 |
| MIMICORE_EXTRACTION_PLAN.md | 提取计划（10 粒，未执行） |
| MIMICORE_IMPORT_AUDIT.md | import 面审计 |
| MIMICORE_L2_ZERO_TOUCH.md | L2 零改动方案 |
| MIMICORE_THREE_RING_USAGE_AUDIT.md | 三环使用审计 |
| MIMIR_MIMICORE_SPRING_SCOPE.md | Spring 期范围声明（P1-5 归档声明依据） |

## 阅读纪律

- 文中结论是**当时**的结论；与代码/现行文档冲突时以代码与 `docs/` 现行为准。
- 文档间相对链接已按新位置修正；跨目录引用（`docs/adr/`、`docs/phase1/`）指向本目录。
- 相关闸：`.mimir-archived-domains.txt` 首行 `mimicore` —— 活树里再 import 该域即被
  `scripts/check_scripts_syntax.py` 判红（ARCHIVED-IMPORT-FAIL）。
