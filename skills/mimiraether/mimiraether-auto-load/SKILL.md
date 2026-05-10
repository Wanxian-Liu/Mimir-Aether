---
auto_load: false
name: mimiraether-auto-load
description: >
  MimirAether Auto-Load — 懒加载策略（尽量不自动注入，按需 skill_view）
---

# 懒加载策略

## 原则
- **只自动注入** 1 个技能：`mimiraether-ralph-core`（~700 chars，编码 Ralph 核心规则）
- 其他所有技能：`auto_load: false`，按需 `skill_view` 加载
- Hermes 的 `plan` skill 也是懒加载的——不需要的就别塞进系统提示

## 审计
`python scripts/audit_skills_auto_load.py`
