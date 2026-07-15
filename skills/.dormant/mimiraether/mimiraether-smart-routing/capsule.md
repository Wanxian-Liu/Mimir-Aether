# [DORMANT] mimiraether-smart-routing

**沉寂时间**: 2026-07-14T18:58:40.833788+00:00
**原始分类**: mimiraether
**描述**: 基于任务特性的智能模型路由 - 根据任务复杂度自动选择合适的模型，降低成本同时保持质量
**触发阈值**: 60天未触碰

---

## 技能要点

# MimirAether Smart Model Routing

## 描述

基于任务特性的智能模型路由 - 根据任务复杂度自动选择合适的模型，降低成本同时保持质量。

**设计来源**: Hermes Agent smart_model_routing 概念，实现于 `agent/smart_model_routing.py`（本仓库）

## 核心设计原则

**保守设计**：仅对明显简单的任务路由到便宜模型，复杂任务保持使用主力模型。

## 简单任务判定规则

### 通过条件（必须全部满足）

| 条件 | 默认值 | 说明 |
|------|--------|------|
| max_simple_chars | 160 | 消息不超过160字符 |
| max_simple_words | 28 | 消息不超过28个词 |
| max_newlines | 1 | 最多1个换行 |
| no_code_blocks | True | 不含代码块（\`\`\` 或 \`） |
| no_urls | True | 不含URL |

### 排除关键词

以下任一关键词出现 → **不使用便宜模型**：

```
debug, debugging, implement, implementation,
refactor, patch, traceback, stacktrace,
exception, error, analyze, analysis,
investigate, architecture, design,
compare, benchmark, optimize, optimise,
review, terminal, shell, tool, tools,
pytest, test, tests, plan, planning,
delegate, subagent, cron, docker, kubernetes
```

## 路由决策流程

```
┌─────────────────────────┐
│  用户消息输入            │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  简单任务检查            │
│  - 字符数 ≤ 160?        │
│  - 词数 ≤ 28?           │
│  - 无代码/URL?           │
│  - 无复杂关键词?         │
└────────────┬────────────┘
             │
       ┌─────┴─────┐
       │           │
      YES          NO
       ▼           ▼
┌──────────┐  ┌──────────────┐
│ 便宜模型  │  │ 主力模型     │
│ cheap_   │  │ primary_     │
│ model    │  │ model        │
└──────────┘  └──────────────┘
```

## 配置格式

```yaml
smart_model_routing:
  enabled: true
  cheap_model:
    provider: openrouter
    model: anthropic/claude-3-haiku
    api_key_env: OPENROUTER_API_KEY
  max_simple_chars: 160
  max_simple_words: 28
```

## 实现参考

```python
def choose_cheap_model_route(user_message: str, routing_config: dict) -> Optional[dict]:
    """Return cheap-model route if message is simple enough."""
    cfg = routing_config or {}
    if not cfg.get("enabled"):
        return None
    
    # 基本检查
    text = user_message.strip()
    if len(text) > cfg.get("max_simple_chars", 160):
        return None
    if len(text.spl

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-smart-routing")` 即可自动唤醒。
