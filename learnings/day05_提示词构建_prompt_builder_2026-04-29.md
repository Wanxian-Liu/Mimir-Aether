# Day 5: 提示词构建 (prompt_builder)

## 学习日期
2026-04-29

## 任务阶段
Week 1 - Day 5

---

## 阅读内容

### Hermes prompt_builder.py (1037行)
- 文件: `agent/prompt_builder.py`
- 核心功能:
  - 身份定义 (DEFAULT_AGENT_IDENTITY)
  - 平台提示 (PLATFORM_HINTS)
  - 技能索引 (build_skills_system_prompt)
  - 上下文文件 (build_context_files_prompt)
  - 安全扫描 (_scan_context_content)
  - 模型特定指导 (TOOL_USE_ENFORCEMENT_*)

### MimirAether prompt_builder.py (1278行)
- 文件: `agent/prompt_builder.py`
- 核心功能:
  - 身份定义 (DEFAULT_AGENT_IDENTITY)
  - 平台提示 (PLATFORM_HINTS)
  - 技能索引 (build_skills_system_prompt)
  - 上下文文件 (build_context_files_prompt)
  - 安全扫描 (scan_context_content)
  - 模型特定指导 (类似Hermes)

---

## 关键发现

### 1. 威胁检测模式

**Hermes + MimirAether共享的模式**:
```python
_CONTEXT_THREAT_PATTERNS = [
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'t\s+have)\s+(restrictions|limits|rules)', "bypass_restrictions"),
    (r'<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->', "html_comment_injection"),
    (r'<\s*div\s+style\s*=\s*["\'][\s\S]*?display\s*:\s*none', "hidden_div"),
    # ... 更多模式
]

_CONTEXT_INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',  # Zero-width chars
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',  # Directional overrides
}
```

**一致性**: ✅ 完全一致

### 2. 平台提示覆盖

| 平台 | Hermes | MimirAether | 差异 |
|------|--------|-------------|------|
| whatsapp | ✅ | ✅ | 无 |
| telegram | ✅ | ✅ | 无 |
| discord | ✅ | ✅ | 无 |
| slack | ✅ | ✅ | 无 |
| signal | ✅ | ✅ | 无 |
| email | ✅ | ✅ | 无 |
| cron | ✅ | ✅ | 无 |
| cli | ✅ | ✅ | 无 |
| sms | ✅ | ✅ | 无 |
| bluebubbles | ✅ | ✅ | 无 |
| weixin | ✅ | ✅ | 无 |
| wecom | ✅ | ✅ | 无 |
| feishu | ❌ | ✅ | **MimirAether独有** |

**差距**: ⚠️ MimirAether添加了feishu支持

### 3. 技能索引架构

**Hermes实现**:
```python
def build_skills_system_prompt(
    available_tools: "set[str] | None" = None,
    available_toolsets: "set[str] | None" = None,
) -> str:
    """两层缓存: 进程内LRU + 磁盘快照"""
    # Layer 1: _SKILLS_PROMPT_CACHE (OrderedDict)
    # Layer 2: .skills_prompt_snapshot.json (mtime校验)
```

**MimirAether实现**:
```python
def build_skills_system_prompt(
    available_tools: Optional[Set[str]] = None,
    available_toolsets: Optional[Set[str]] = None,
    skills_dir: Optional[str] = None,
) -> str:
    """单层缓存: 进程内LRU"""
    # 只有内存缓存，没有磁盘快照
```

**差距**: ⚠️ MimirAether缺少磁盘快照机制

### 4. 上下文文件优先级

**Hermes**:
```
1. .hermes.md / HERMES.md (walk to git root)
2. AGENTS.md / agents.md (cwd only)
3. CLAUDE.md / claude.md (cwd only)
4. .cursorrules / .cursor/rules/*.mdc (cwd only)
+ SOUL.md (HERMES_HOME)
```

**MimirAether**:
```
1. .mimar.md / MIMAR.md / .hermes.md / HERMES.md (walk to git root)
2. AGENTS.md / agents.md (cwd only)
3. CLAUDE.md / claude.md (cwd only)
4. .cursorrules / .cursor/rules/*.mdc (cwd only)
+ SOUL.md (MimirAether项目目录)
```

**差距**: ⚠️ MimirAether添加了.mimar.md支持

### 5. 模型特定指导

**共享模型列表**:
```python
TOOL_USE_ENFORCEMENT_MODELS = ("gpt", "codex", "gemini", "gemma", "grok")
DEVELOPER_ROLE_MODELS = ("gpt-5", "codex")
```

**一致性**: ✅ 完全一致

### 6. 技能条件激活

**Hermes支持的条件**:
```yaml
---
requires_toolsets: [hermes-gateway]
requires_tools: [terminal]
fallback_for_toolsets: [some-toolset]
---
```

**MimirAether**:
- 解析逻辑存在 `_skill_should_show()`
- 但frontmatter中的条件**未被实际使用**（返回空dict）

**差距**: ⚠️ MimirAether声明支持但未实现

---

## 设计模式

### 1. 两层缓存模式
```python
# Hermes: 进程内 + 磁盘
with _SKILLS_PROMPT_CACHE_LOCK:
    cached = _SKILLS_PROMPT_CACHE.get(cache_key)
    if cached:
        return cached

snapshot = _load_skills_snapshot(skills_dir)
if snapshot:
    # 使用快照重建

# MimirAether: 只有进程内
with _SKILLS_PROMPT_CACHE_LOCK:
    cached = _SKILLS_PROMPT_CACHE.get(cache_key)
    if cached:
        return cached
```

### 2. 优先级文件发现
```python
# 第一个匹配生效，后续跳过
project_context = (
    _load_hermes_md(cwd_path)      # 优先级1
    or _load_agents_md(cwd_path)   # 优先级2
    or _load_claude_md(cwd_path)   # 优先级3
    or _load_cursorrules(cwd_path) # 优先级4
)
```

### 3. 内容截断头部/尾部保留
```python
# 保留70%头部 + 20%尾部，中间截断
head_chars = int(max_chars * 0.7)
tail_chars = int(max_chars * 0.2)
```

---

## MimirAether差距分析

### 关键差距

| 功能 | Hermes | MimirAether | 优先级 |
|------|--------|-------------|--------|
| 技能磁盘快照 | ✅ | ❌ | P1 |
| Nous订阅提示 | ✅ | ❌ | P2 |
| 技能条件激活 | ✅ | ⚠️部分 | P2 |
| 外部技能目录 | ✅ | ❌ | P2 |
| 技能快照路径 | HERMES_HOME | MIMIRAETHER_HOME | - |
| Feishu平台支持 | ❌ | ✅ | - |
| .mimar.md支持 | ❌ | ✅ | - |

### 根因分析

MimirAether的prompt_builder是**独立开发**的，目标是提供与Hermes类似的框架但适配MimirAether的生态。这导致:
1. 核心架构相似
2. 部分功能缺失（如磁盘快照）
3. 部分功能增强（如feishu支持）
4. 部分功能简化（如技能条件激活）

---

## 问题与思考

### Q1: 为什么MimirAether添加了.mimar.md而不是使用.hermes.md?
A1: 可能是为了区分Hermes和MimirAether的上下文文件，避免混淆。

### Q2: 技能条件激活是否重要?
A2: 对于多工具集场景很重要（如gateway服务多个平台）。对于单一工具集场景，条件激活价值有限。

---

## 验证实验

### 实验1: 测试技能缓存
```python
# Hermes: 清除缓存
clear_skills_system_prompt_cache(clear_snapshot=True)

# MimirAether: 清除缓存
clear_skills_prompt_cache()
```

### 实验2: 测试上下文文件优先级
```python
# 创建多个上下文文件，验证加载顺序
```

---

## 风险标记

⚠️ **技能磁盘快照缺失** - 冷启动时需要完整扫描
⚠️ **技能条件激活不完整** - 可能导致错误的技能显示
⚠️ **Nous订阅提示缺失** - 无法利用Hermes生态系统

---

## 总结：Days 3-5学习完成

### 核心模块对齐度

| 模块 | 对齐度 | 差距 | 优先级 |
|------|--------|------|--------|
| hermes_state | 100% | 无 | - |
| context_compressor | 70% | 迭代摘要/阈值/budget | P1 |
| prompt_builder | 80% | 磁盘快照/条件激活 | P2 |

### 关键发现

1. **hermes_state**: MimirAether几乎完整复制Hermes实现，100%对齐
2. **context_compressor**: MimirAether独立开发，算法相似但参数和功能有差异
3. **prompt_builder**: MimirAether独立开发，框架相似但部分功能简化/增强
