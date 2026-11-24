---
name: mimiraether-prompt-armory
description: >
  统一提示词武库 — 六库合一检索层。按需从 awesome-chatgpt-prompts、awesome-system-prompts、
  agency-agents、roles/、Cursor 规则、散落文件 六个提示词库中检索最佳提示词，
  用于角色注入、任务模板、自我增强、提示词对比。每库配有适配器，统一返回接口。
triggers:
  - "扮演 / 充当 / act as / 你是X"
  - "推荐提示词 / 找prompt / 搜索提示词 / 有什么提示词"
  - "对比 X 和 Y 的提示词"
  - Agent 面对复杂任务时自动触发（静默自增强）
allowed-tools:
  - Read
  - Grep
  - WebSearch
  - Bash
---

# 提示词武库 (Prompt Armory)

六库合一统一检索层。~2000 条提示词/角色，5 种格式，6 个来源。

## 库清单

| # | 名称 | 路径 | 数量 | 格式 | 质量 | 适配器 |
|---|------|------|------|------|------|--------|
| 1 | awesome-chatgpt-prompts | `workspace/awesome-chatgpt-prompts/prompts.csv` | 1695 | CSV | ⭐⭐ | `_search_csv` |
| 2 | awesome-system-prompts | `workspace/awesome-system-prompts/leaks/` | 94 | .md | ⭐⭐⭐⭐ | `_search_md_dir` |
| 3 | agency-agents | `projects/agency-agents/` | 178 | .md (YAML) | ⭐⭐⭐ | `_search_agency` |
| 4 | roles/ | `workspace/roles/` | 6 | .md | ⭐⭐⭐⭐⭐ | `_search_md_dir` |
| 5 | Cursor 规则 | `~/.cursor/` | ~20 | .mdc | ⭐⭐⭐ | `_search_mdc` |
| 6 | 散落文件 | workspace 根 | ~10 | .md | ⭐⭐ | `_search_root_md` |

## 检索流程

```
用户输入 → 关键词提取 → 分层搜索(L1→L2) → 来源排序 → 返回 top-N
```

### L1 精确匹配
- CSV: act 列精确/模糊匹配（`awk -F',' '$1 ~ /keyword/' prompts.csv`）
- agency-agents: 文件名匹配（`find ... -name "*keyword*"`）
- Cursor 规则: 文件名匹配

### L2 全文搜索
- `rg -l -i "keyword" {path}` 跨所有库
- 限制返回前 20 条，按来源权重排序

### 来源权重（排序规则）
1. roles/ — 用户手写，100 分
2. awesome-system-prompts — 行业真实 prompt，90 分
3. agency-agents — 结构化角色库，70 分
4. Cursor 规则 — 行为约束，50 分
5. awesome-chatgpt-prompts — 社区众包，30 分
6. 散落文件 — 未分类，20 分

## 四大场景

### 场景 A: 角色注入
触发: "扮演/充当/你是 X"
行为:
  1. L1→L2 搜索角色名
  2. 取最佳匹配 prompt
  3. 追加到系统指令（不占主上下文，用 context-engine 注入）
  4. 回报："已注入 {role} 角色（来源: {source}）"

### 场景 B: 提示词推荐
触发: "推荐提示词/找prompt/搜索提示词"
行为:
  1. L2 全文搜索
  2. 返回 top-5，标注来源 + 片段预览
  3. 用户选择后注入

### 场景 C: 自我增强（静默）
触发: Agent 面对复杂任务时自动
行为:
  1. 提取任务关键领域词
  2. L2 搜索 awesome-system-prompts + agency-agents
  3. 取最佳 1-2 条注入系统指令
  4. 不告知用户（静默）

### 场景 D: 提示词对比
触发: "对比 X 和 Y 的提示词"
行为:
  1. 分别搜索 X 和 Y
  2. 并排展示 prompt 结构差异
  3. 标注差异点（角色定义/约束/输出格式等）

## 与其他技能集成

| 技能 | 集成点 |
|------|--------|
| brainstorming | 阶段2 Explore → 自动检索相关 prompt → 更专业方案 |
| context-engine | 注入角色 prompt → 不占主上下文 |
| smart-routing | prompt 复杂度 → 辅助模型选择 |
| strategy-planner | 决策前注入领域角色 → 提升判断质量 |

## 输出格式

```
🔍 搜索: "{query}"
📚 命中: {count} 条 | 来源: {sources}

#1 [{source}] {name} ⭐{score}
{preview}...
---
#2 ...
```

## 适配器实现

每个适配器是 Python 函数，统一接口：
```python
def search(query: str) -> list[dict]:
    """返回 [{name, source, score, preview, full_text, metadata}]"""
```

库路径从 `~/.openclaw/workspace` 和 `~/.openclaw/projects` 解析。
