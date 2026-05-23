# 胶囊 + insights 勘探报告

**日期**：2026-05-21  
**来源**：EV-X01 + EV-X02

## EV-X01：胶囊管线（produce_capsule）

### 调用链
```
飞书消息 → agent/core_loop → produce_capsule tool
  → tools/mimircore_tool.py:_handle_produce_capsule() (L237)
  → mimicore.capsule_generator.generate()
  → GDI 评分 ≥70 → 写入 memory/capsules/*.html
```

### 判定：非空壳 ✅

| 层 | 文件 | 代码量 | 状态 |
|----|------|--------|:--:|
| 工具注册 | `tools/mimircore_tool.py` | 521 行 | ✅ 4 个胶囊工具完整（produce/list/get/improve） |
| 工具入口 | `tools/toolsets.py` L194 | — | ✅ 注册到 mimircore toolset |
| 安全审计 | `agent/tool_guard.py` | — | ✅ 风险等级标注 |
| 核心引擎 | `mimicore/capsule_generator.py` | submodule | ✅ 外部依赖（submodule） |

### 结论
胶囊管线从工具注册→安全审计→Mimir-Core调用→落盘完整可用。**非空壳，无需修复。**

## EV-X02：insights 模块

### 实际状态

| 层 | 路径 | 状态 |
|----|------|:--:|
| SKILL.md | `skills/productivity/insights/SKILL.md` | ✅ 描述完整 |
| Python 实现 | `agent/insights.py` | ✅ 存在（E-006 依赖 D6-0a） |
| 工具注册 | — | ⚠️ 未查（E-006 范围） |

### 结论
insights 有真实 Python 模块（非空壳），但 E-006 的 D6-0a（TOOL_CALL 表）未完成。

## 总体

- EV-X01：胶囊管线 ✅ 健康，无需介入
- EV-X02：insights ✅ 有代码但 E-006 未完成 → 属 E-006 范围
- EV-X 轨无需新建修复任务
