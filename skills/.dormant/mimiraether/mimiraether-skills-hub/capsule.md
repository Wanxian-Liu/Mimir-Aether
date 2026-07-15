# [DORMANT] mimiraether-skills-hub

**沉寂时间**: 2026-07-14T18:58:40.789034+00:00
**原始分类**: mimiraether
**描述**: Hermes Agent Skills Hub技能中心 - 统一的技能管理和分发系统，支持技能浏览、安装、搜索和发布
**触发阈值**: 60天未触碰

---

## 技能要点

# MimirAether Skills Hub — 技能中心使用指南

## 简介

Hermes Agent 的 Skills Hub 是一个统一的技能管理和分发系统。本技能记录其完整功能，供 MimirAether 在集成或扩展技能管理时参考。

---

## 核心命令

### 1. browse — 浏览技能库

浏览所有可用技能（分页显示）。

```
hermes skills browse [--page N] [--size N] [--source official|skills-sh|well-known|github|clawhub|all]
```

**示例：**
```
hermes skills browse                           # 浏览第1页，每页20条
hermes skills browse --page 2 --size 50       # 浏览第2页，每页50条
hermes skills browse --source official        # 只看官方技能
```

**输出特点：**
- 官方技能始终优先显示
- 按信任级别排序（builtin > trusted > community）
- 显示来源和安装数统计
- 慢速源超时后显示警告

---

### 2. search — 搜索技能

在注册表中搜索技能。

```
hermes skills search <query> [--source SOURCE] [--limit N]
```

**示例：**
```
hermes skills search kubernetes
hermes skills search "code review" --limit 20
hermes skills search github --source github
```

---

### 3. install — 安装技能

安装技能（包含安全扫描）。

```
hermes skills install <identifier> [--category CATEGORY] [--force] [--now]
```

**参数说明：**
- `identifier` - 技能标识符，格式：`source/category/name`（如 `official/autonomous-ai-agents/claude-code`）
- `--category` - 安装到的分类目录
- `--force` - 强制重新安装
- `--now` - 立即生效（清除提示缓存）

**安装流程：**
1. 从注册表获取技能元数据和文件
2. 隔离到临时目录（quarantine）
3. 运行安全扫描（skills_guard）
4. 检查安装策略（allow/block）
5. 显示上游元数据（GitHub stars、安装数等）
6. 用户确认后复制到 **`$(git rev-parse --show-toplevel)/skills/`**（仓库内技能树）或 **`$MIMIR_AETHER_HOME/skills/`**（若将技能装到运行时数据根）

**示例：**
```
hermes skills install official/autonomous-ai-agents/claude-code
hermes skills install github/openai/codex --force
```

**短名称解析：**
不带斜杠的名称会自动搜索解析：
```
hermes skills install claude-code   # 自动搜索并解析完整identifier
```

---

### 4. inspect — 预览技能

不安装，直接查看技能内容。

```
hermes skills inspect <identifier>
```

**示例：**
```
hermes skills inspect official/autonomous-ai-agents/blackbox
hermes skills inspect claude-code   # 短名称自动解析
```

**输出内容：**
- 技能名称、描述、来源、信任级别
- 标签
- SKILL.md 前50行预览

---

### 5. list — 列出已安装技能

```
hermes skills list [--source hub|builtin|local|all]
```

**来源类型：**
- `hub` - 从 Skills Hub 安装的第三方技能
- `built

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-skills-hub")` 即可自动唤醒。
