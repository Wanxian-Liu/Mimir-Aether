---
description: Hermes Agent Skills Hub技能中心 - 统一的技能管理和分发系统，支持技能浏览、安装、搜索和发布
---

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
6. 用户确认后复制到 `~/.hermes/skills/`

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
- `builtin` - 内置技能
- `local` - 本地自定义技能

**示例：**
```
hermes skills list
hermes skills list --source hub
```

---

### 6. check — 检查更新

检查已安装的 Hub 技能是否有更新。

```
hermes skills check [name]
```

**示例：**
```
hermes skills check              # 检查所有
hermes skills check claude-code # 检查指定技能
```

---

### 7. update — 更新技能

更新已安装的 Hub 技能到最新版本。

```
hermes skills update [name]
```

---

### 8. audit — 安全审计

对已安装的 Hub 技能重新运行安全扫描。

```
hermes skills audit [name]
```

---

### 9. uninstall — 卸载技能

```
hermes skills uninstall <name> [--now]
```

---

### 10. publish — 发布技能

将本地技能发布到 GitHub（通过 PR）。

```
hermes skills publish <skill-path> --to github --repo owner/repo
```

**流程：**
1. 验证 SKILL.md 存在且有 description
2. 自我安全扫描
3. Fork 目标仓库
4. 创建新分支
5. 上传技能文件
6. 创建 Pull Request

---

### 11. tap — 管理自定义源

添加自定义 GitHub 仓库作为技能源。

```
hermes skills tap list
hermes skills tap add owner/repo [--path skills/]
hermes skills tap remove owner/repo
```

---

### 12. snapshot — 配置快照

导出/导入技能配置。

```
hermes skills snapshot export <file>
hermes skills snapshot import <file> [--force]
```

**用途：**
- 备份当前技能配置
- 在新机器上快速恢复
- 版本控制技能列表

---

## 内部实现要点

### Source Router（源路由器）

通过 `create_source_router()` 创建，支持多个源：
- `official` - Nous Research 官方可选技能
- `skills-sh` - Skills.sh 社区注册表
- `well-known` - Well-known 索引
- `github` - GitHub 仓库
- `clawhub` - ClawHub 市场
- `lobehub` - LobeHub
- 自定义 taps - 用户添加的 GitHub 仓库

### 信任级别

| 级别 | 说明 |
|------|------|
| `builtin` | Hermes 内置 |
| `trusted` | 官方维护的社区技能 |
| `community` | 社区提交 |

### 安全扫描

`tools.skills_guard` 模块负责：
- AST 分析检测恶意代码模式
- 文件路径检查（防止路径遍历）
- shell 命令分析
- 可疑模式识别

### HubLockFile

记录已安装技能的状态：
```json
{
  "name": "claude-code",
  "identifier": "official/autonomous-ai-agents/claude-code",
  "source": "official",
  "trust_level": "builtin",
  "install_path": "autonomous-ai-agents/claude-code",
  "version": "1.0.0"
}
```

---

## 斜杠命令格式

在交互式聊天中可使用 `/skills` 前缀：

```
/skills search kubernetes
/skills install claude-code --force
/skills inspect openai/skills/skill-creator
/skills list --source hub
/skills check
/skills update
/skills audit my-skill
/skills uninstall my-skill
/skills tap list
/skills tap add owner/repo
/skills tap remove owner/repo
```

---

## 参考资料

- 源码：`~/.openclaw/projects/hermes-agent/hermes_cli/skills_hub.py`
- 核心模块：`~/.openclaw/projects/hermes-agent/tools/skills_hub.py`
- 安全扫描：`~/.openclaw/projects/hermes-agent/tools/skills_guard.py`
