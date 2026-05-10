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

## auto_load 策略（与运行时一致）

实现位置：`agent/prompt_builder.py` 的 `_build_auto_load_skills_prompt`：扫描 `SKILL.md` 的 YAML frontmatter，仅当 **`auto_load: true`**（布尔真）时把该技能注入系统提示。

- **默认**：非会话关键技能**不要**开 `auto_load: true`，按需 `skill_view`；可选显式写 `auto_load: false` 表达意图。
- **建议自动注入**：与 NEXT_SESSION / 元规则强绑定的技能（示例：`mimiraether-tool-triggers`、`mimiraether-cross-session`、`mimiraether-plan-mode`、`hermes-cat-write`、`mimiraether-context-compressor`、本说明、`mimiraether-paralysis-break`、`mimiraether-heartbeat` 等）。
- **注入长度**：若 frontmatter 含顶层 `description` 或 `auto_load_meta.description`，运行时只注入该短文案；否则回退为正文前 **2000** 字符（避免提示膨胀）。
- **审计**：仓库根执行 `python scripts/audit_skills_auto_load.py` 列出所有 `SKILL.md` 的 `auto_load` 状态（报告用，退出码恒为 0）。
