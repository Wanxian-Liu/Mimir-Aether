# [DORMANT] mimiraether-skill-solidify

**沉寂时间**: 2026-07-23T06:18:46.665425+00:00
**原始分类**: mimiraether
**描述**: 将可复用经验固化为 SKILL.md 的流程：何时做、落盘路径、命名、frontmatter、skill_manage 操作与质量清单（配合 mimiraether-tool-triggers）。
**触发阈值**: 60天未触碰

---

## 技能要点

# MimirAether Skill 固化流程

本技能是 **persistent 第 4 条药方（skill 固化）** 的操作手册。  
**触发意识**见 `skill_view('mimiraether-tool-triggers')` 中的 **skill_manage** 小节；本文件负责 **怎么做**。

## 运行时真源（路径）

主 Agent 注册的 `skill_manage` 来自 **`skills/skills_loader.py`**（由 `agent/core_loop` 注册），写入的是 **本仓库内的 `skills/`** 目录：

- 指定 `category` 时：`skills/<category>/<name>/SKILL.md`
- 未指定 `category` 时：先尝试 `skills/<name>/`；若不存在则落到 **`skills/general/<name>/SKILL.md`**

若你读到 `tools/skill_manager_tool.py` 里关于 `~/.openclaw/mimir-aether/skills/` 的说明，那是独立工具模块的文档；**与当前 Agent 行为冲突时，以本技能与 `skills_loader` 为准**。

## 何时固化

**值得固化：**

- 复杂任务刚跑通（通常 **5+** 次工具调用）且模式会再现
- 踩过坑并形成了**可重复的步骤或命令**
- 多工具组合才搞定的工作流，希望下次一键按图索骥
- 用户明确要求「记下来 / 做成技能」

**反模式：**

- 调试很累但从不 `skill_manage`
- 发现已加载的 skill 有错，只临时绕过、不 `patch`

**自检一句：**「下次还会遇到吗？会 → 固化或 patch。」

## 命名与分类

- **name**（技能目录名）：小写字母、数字、`.`、`_`、`-`；建议与 frontmatter 里 `name` 字段一致；长度建议 ≤ 64（与 `tools/skill_manager_tool.py` 中 `MAX_NAME_LENGTH` / `VALID_NAME_RE` 对齐）。**注意**：`skills_loader` 的 `create` 未必自动做同名校验，仍请手遵守，便于以后统一。
- **category**：单一目录段，规则同上；用于仓库内归类（如 `mimiraether`、`software-development`）。团队共享的 Mimir 约定技能优先放在 `skills/mimiraether/`。

## Frontmatter（最小可用）

```yaml
---
name: your-skill-name
description: Use when <触发>. <一句话行为>.
version: 1.0.0
---
```

- **`description`**：≤ 1024 字符（与 loader / 校验约定一致）。
- 更完整的 in-repo 结构、标签与拆 `references/` 的写法：见 `skill_view('hermes-agent-skill-authoring')`。

**手工校验**：创建或大幅编辑后，可对照 `tools/skill_manager_tool.py` 中的 `_validate_frontmatter` 规则（必须以 `---` 开头、闭合 `---`、YAML 可解析、含 `name`/`description`、正文非空）。Agent 走 `skills_loader` 时**不会**自动替你跑该校验，遗漏会导致难排查的格式问题。

## skill_manage 操作顺序

1. **`create`**：准备好**完整** `SKILL.md` 字符串（frontmatter + 正文），调用 `skill_manage(action='create', name='...', content='...', category='...'可选)`。  
   - 成功后用 `skill_view(name)` 通读验收。
2. **小改**：优先 **`patch`**（`old_string` / `new_string`，可选 `file_path` 指向子文件）。  
3. **大改**：**`edit`** 提交整份新 `content`（仅当 patch 不划算时）。  
4. **附属文件**：**`write_file`**（如 `references/notes.md`）；删除用 **`remove_file`**。

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-skill-solidify")` 即可自动唤醒。
