---
auto_load: true
auto_load_meta:
  triggers:
  - 会话启动
  - 跨会话
  - 持久化
  - 记忆
  - persistent
  - memory
  priority: highest
  description: 每次会话启动时自动加载，确保跨会话记忆自动恢复
description: 每次会话启动时自动加载，确保跨会话记忆自动恢复
---


# mimiraether-cross-session

## name

MimirAether Cross-Session — 跨会话持久化

## description

实现MimirAether在多个会话之间的状态持久化和信息共享。包括用户偏好跨会话保持、项目上下文延续和未完成任务的状态恢复。

## 核心原理

跨会话记忆的核心不是"记住一切"，而是**只记住下个会话启动时最需要的东西**。

三环过滤：
1. **什么值得记** → 只有影响未来决策的才记（偏好、决策、未完成任务）
2. **什么不值得记** → 不记过程日志、已完成任务细节、临时状态
3. **什么该过期** → 完成的任务自动移除、超过3次会话未引用的记忆归档

## 自动注入路径

每次会话启动时，按以下顺序恢复跨会话状态：

```
Step 1: 读取 data/persistent.json（会话状态）
  ├── identity → 确认"我是谁"
  ├── memory.key_decisions → 恢复关键决策
  ├── memory.user_preferences → 恢复用户偏好
  ├── progress.pending_tasks → 恢复未完成任务
  └── progress.completed_milestones → 确认已完成项

Step 2: 读取 memory/persistent.json（记忆持久化）
  ├── 检查 session_boundary 条目 → 恢复上次会话摘要
  └── 检查 meta_rules → 恢复跨会话硬约束

Step 3: 差异检测
  ├── 对比 data/persistent.json 和 memory/persistent.json
  ├── 检测版本号 → 如果版本不匹配，执行迁移
  └── 检测 session_count → 确认无会话丢失

Step 4: 自动注入到系统提示
  ├── 将 key_decisions 注入为"已知决策"
  ├── 将 pending_tasks 注入为"待完成"
  └── 将 user_preferences 注入为"用户偏好"
```

## 核心功能列表

- **偏好持久化**：保存和恢复用户的交互偏好、工具设置和常用配置
- **项目状态延续**：跨会话追踪项目进度、待办事项和决策历史
- **任务恢复**：中断任务自动保存状态，下个会话可继续执行
- **会话历史检索**：通过session_search搜索跨会话历史记录
- **上下文传递**：将重要上下文从上一会话传递到新会话
- **增量同步**：轻量级状态同步，避免重复加载大型数据
- **差异检测**：自动检测版本变化和会话丢失
- **过期机制**：超过3次会话未引用的记忆自动归档

## 会话结束时的保存流程

每轮会话结束时（或关键决策点），执行：

```python
import json, os

def save_session_boundary(summary, key_decisions, pending_tasks, meta_rules=None):
    """保存会话边界，供下个会话恢复"""
    
    # 1. 更新 data/persistent.json
    data_path = "data/persistent.json"
    data = json.load(open(data_path)) if os.path.exists(data_path) else {}
    
    data["last_session_end"] = "当前时间"
    data["session_count"] = data.get("session_count", 0) + 1
    if "memory" not in data:
        data["memory"] = {}
    data["memory"]["key_decisions"] = key_decisions
    data["memory"]["learned_patterns"] = data["memory"].get("learned_patterns", [])
    data["progress"]["pending_tasks"] = pending_tasks
    data["progress"]["completed_milestones"] = data["progress"].get("completed_milestones", [])
    
    json.dump(data, open(data_path, "w"), indent=2, ensure_ascii=False)
    
    # 2. 更新 memory/persistent.json
    memory_path = "memory/persistent.json"
    memory = json.load(open(memory_path)) if os.path.exists(memory_path) else {"counter": 0, "entries": []}
    
    memory["counter"] += 1
    memory["entries"].append({
        "id": f"session-end-{memory['counter']}",
        "type": "session_boundary",
        "timestamp": "当前时间",
        "content": {
            "summary": summary,
            "key_decisions": key_decisions,
            "pending_tasks": pending_tasks,
            "meta_rules": meta_rules or []
        }
    })
    
    # 3. 过期检查：只保留最近20条
    if len(memory["entries"]) > 20:
        memory["entries"] = memory["entries"][-20:]
    
    json.dump(memory, open(memory_path, "w"), indent=2, ensure_ascii=False)
```

## 关键决策点（触发保存）

以下情况自动触发会话状态保存：
1. **完成一个重要里程碑** → 标记完成 + 更新 pending_tasks
2. **发现用户偏好** → 更新 user_preferences
3. **做出影响未来的决策** → 更新 key_decisions
4. **会话即将结束** → 保存完整边界
5. **安装/配置了新的工具** → 更新 environment
