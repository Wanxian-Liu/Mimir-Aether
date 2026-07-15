# [DORMANT] snippets

**沉寂时间**: 2026-07-14T18:58:41.205737+00:00
**原始分类**: productivity
**描述**: 快速保存、搜索和复用常用代码片段。支持标签分类和快速检索。
**触发阈值**: 60天未触碰

---

## 技能要点

# 代码片段管理 (snippets)

## 用途
快速保存、搜索和复用常用代码片段。支持标签分类和快速检索。

## Agent 集成工作流

### 遇到可复用代码 → 保存
当你在当前会话中写出了有价值的代码，主动提议：
```
这个 [脚本/函数/命令] 值得保存为 snippet。
> snippet save "name" python "..."
```

### 搜索优先于重写
需要某类代码时，先搜索 snippet 库：
```
> snippet search "regex email"
找到: email-validate (python), email-regex (bash)
```
避免重复编写已保存的代码。

### 批量导入
从聊天中提取多个片段：
```bash
# 保存多个相关片段
snippet save "api-auth" python '...'
snippet save "api-client" python '...'
snippet save "api-types" python '...'
# 统一标签
snippet tag "api-*" --add api
```

## 核心操作

### 保存片段
```bash
snippet save <name> <language> "<content>" [--tag <t1,t2>]
# 示例
snippet save "http-retry" python '
import requests
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
def fetch(url):
    return requests.get(url, timeout=10)
'
```

### 搜索片段
```bash
snippet search <keyword> [--lang <language>] [--tag <tag>]
# 示例
snippet search "retry" --lang python
snippet search "" --tag api  # 列出所有api标签片段
```

### 列出所有片段
```bash
snippet list [--lang <language>] [--tag <tag>]
```

### 使用片段
```bash
snippet show <name>           # 查看内容
snippet use <name>            # 输出到stdout，可管道
snippet use <name> | pbcopy   # 复制到剪贴板
snippet use <name> --execute  # 直接执行（仅限安全语言）
```

### 管理标签
```bash
snippet tag <name> --add <tag>
snippet tag <name> --remove <tag>
snippet tags                   # 列出所有标签
```

### 删除
```bash
snippet rm <name>
```

## 标签约定

| 标签 | 用途 |
|------|------|
| `api` | API 客户端/封装 |
| `cli` | 命令行工具 |
| `algo` | 算法/数据结构 |
| `regex` | 正则表达式 |
| `shell` | Shell 脚本 |
| `config` | 配置文件模板 |
| `test` | 测试代码 |
| `util` | 通用工具函数 |

## 搜索策略

1. **精确搜索**: `snippet search "function_name"` — 找特定函数
2. **模糊搜索**: `snippet search "auth"` — 找相关主题
3. **标签筛选**: `snippet search "" --tag api` — 按领域浏览
4. **语言限定**: `snippet search "sort" --lang python` — 限定语言

## 实现方式
- 存储位置: `~/.snippets/`
- 每个片段一个JSON文件: `{name, language, content, tags[], created, updated}`
- 索引文件: `~/.snippets/index.json`

## 依赖
- jq (用于JSON处理)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("snippets")` 即可自动唤醒。
