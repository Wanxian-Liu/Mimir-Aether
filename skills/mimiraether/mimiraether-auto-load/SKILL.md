---
auto_load: true
name: mimiraether-auto-load
description: MimirAether Auto-Load — 智能上下文自动加载
---

# mimiraether-auto-load

## name

MimirAether Auto-Load — 智能上下文自动加载

## description

根据当前任务类型和会话历史，自动推断并加载相关技能(Skills)和记忆上下文。减少手动干预，提升AI助手的即战力。

## 核心功能列表

- **任务类型检测**：分析用户输入，识别所需技能领域
- **自动技能加载**：根据任务匹配度自动调用skill_view加载相关技能
- **上下文优先级排序**：根据任务相关性排序要加载的技能和记忆
- **缓存优化**：记录频繁使用的技能组合，加速后续加载
- **可配置规则**：支持用户定义自动加载规则和白名单
- **回退机制**：当自动加载失败时，提示用户手动选择技能
