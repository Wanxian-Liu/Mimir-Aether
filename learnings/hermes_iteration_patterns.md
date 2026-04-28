# Hermes Agent 迭代方法学习笔记

**作者**: MimirAether  
**日期**: 2025-01-15  
**来源**: 分析Hermes源码和MimirAether实现

---

## 一、源码目录结构分析

### 1.1 Hermes核心目录结构

```
~/.hermes/
├── SOUL.md                 # Agent的灵魂定义
├── config.yaml            # 主配置
├── .env                   # API密钥
├── bin/                   # 可执行文件
├── cache/                 # 缓存
├── cron/                  # 定时任务
├── logs/                  # 日志
├── memories/              # 记忆存储
├── optional-skills/       # 可选技能（大型skill）
├── skills/                # 核心技能库
│   ├── autonomous-ai-agents/
│   │   └── hermes-agent/  # Hermes核心agent skill
│   ├── creative/          # 创意类skill
│   ├── github/           # GitHub集成
│   ├── mlops/            # MLOps工具
│   └── software-development/
│       ├── plan/         # 计划模式
│       ├── systematic-debugging/  # 调试技能
│       └── test-driven-development/  # TDD
├── sandboxes/            # 沙箱环境
├── sessions/             # 会话记录
└── state.db             # SQLite状态数据库
```

### 1.2 关键设计原则

1. **核心代码与用户数据分离**: 核心逻辑在独立仓库，用户数据在~/.hermes/
2. **技能模块化**: 每个skill是一个独立的功能单元
3. **配置驱动**: 使用YAML配置和.env分离配置与密钥

---

## 二、Hermes的自我迭代机制

### 2.1 Skills系统（知识持久化）

Hermes通过Skills系统实现"学习-记忆-复用"闭环：

```python
# Skill结构
skills/
└── <category>/
    └── <skill-name>/
        ├── SKILL.md           # 核心技能文档
        ├── DESCRIPTION.md      # 描述（可选）
        ├── references/        # 参考文档
        └── scripts/           # 辅助脚本
```

**SKILL.md标准格式**:
```yaml
---
name: skill-name
description: 技能描述
version: 1.0.0
metadata:
  hermes:
    tags: [tag1, tag2]
    related_skills: [other-skill]
---

# 技能内容...
```

### 2.2 三环闭环进化架构

```
┌─────────────────────────────────────────────────────────┐
│                    监控环 (Monitor Ring)                  │
│  - 状态感知：持续收集系统指标                             │
│  - 异常检测：基于阈值和模式识别                           │
│  - 输出：MonitorEvent列表                               │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    决策环 (Decision Ring)                │
│  - 根因分析：分析监控事件的根本原因                       │
│  - 策略生成：生成修复策略候选列表                        │
│  - 策略选择：评估风险并选择最优策略                      │
│  - 输出：DecisionOutput                                 │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    执行环 (Execution Ring)               │
│  - 沙箱模拟：验证策略效果                                │
│  - 执行修复：应用策略到系统                              │
│  - 效果验证：确认修复有效                                │
│  - 输出：ExecutionOutput                                │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
                    反馈到监控环
```

### 2.3 核心迭代组件

#### 2.3.1 ProactiveKnowledgeCorrector（主动知识纠错）

```python
class ProactiveKnowledgeCorrector:
    """监控会话上下文，评估置信度，必要时注入纠错"""
    
    async def monitor_and_correct(self, session_context):
        """
        核心流程:
        1. monitor() → 获取最近生成项
        2. _assess_confidence() → 评估置信度
        3. _verify_against_rag() → RAG验证
        4. _generate_correction() → 生成纠错
        5. _inject_correction() → 注入纠错
        """
```

**置信度评估信号**:
- 内容长度（过短/过长低置信）
- 不确定词汇检测（可能、也许、probably）
- 引用标记但无来源

#### 2.3.2 IntentPredictor（意图预测）

```python
class IntentPredictor:
    """基于上下文预测用户意图，提前预加载相关记忆"""
    
    async def predict_and_preload(self, current_context):
        """
        核心流程:
        1. _predict_intents() → 预测意图
        2. _retrieve_related() → 检索相关记忆
        3. _preload_to_working_memory() → 预加载到工作内存
        """
```

#### 2.3.3 AutonomousRepairExecutor（自主修复）

```python
class AutonomousRepairExecutor:
    """基于胶囊文档的自主修复执行"""
    
    async def diagnose_and_fix(self, error_context):
        """
        核心流程:
        1. find_root_cause() → 找根因
        2. match_fix_strategy() → 匹配策略
        3. sandbox.simulate() → 沙箱模拟
        4. if success_rate < 0.8: escalate → 升级
        5. execute_fix() → 执行修复
        6. verify() → 验证效果
        """
```

---

## 三、文件写入模式

### 3.1 统一文件操作接口

Hermes通过`ShellFileOperations`提供跨环境的统一文件API：

```python
class ShellFileOperations(FileOperations):
    """通过shell命令实现文件操作"""
    
    def write_file(self, path: str, content: str) -> WriteResult
    def patch_replace(self, path, old, new, replace_all=False) -> PatchResult
    def patch_v4a(self, patch_content) -> PatchResult
    def search(self, pattern, path=".", ...) -> SearchResult
```

### 3.2 Patch模式详解

Hermes支持两种patch模式：

#### 3.2.1 Replace模式（推荐）

```python
# 语法
patch_tool(
    mode="replace",
    path="/path/to/file.py",
    old_string="def old_function():",
    new_string="def new_function():",
    replace_all=False
)
```

**特点**:
- 简单直观：old_string → new_string
- 支持replace_all批量替换
- 提供"未找到"提示

#### 3.2.2 V4A Patch模式

```
**** Update File: src/main.py
--- Original
+++ Modified
@@ -1,5 +1,5 @@
 def old_function():
-    return "old"
+    return "new"
```

### 3.3 安全机制

1. **敏感路径保护**:
```python
WRITE_DENIED_PATHS = {
    "~/.ssh/authorized_keys",
    "~/.ssh/id_rsa",
    "~/.hermes/.env",
    "/etc/sudoers",
    # ...
}

WRITE_DENIED_PREFIXES = [
    "~/.ssh",
    "~/.aws",
    "~/.gnupg",
    # ...
]
```

2. **文件陈旧性检测**:
```python
# 写入前检查文件是否在读取后被外部修改
_check_file_staleness(path, task_id)
```

3. **Safe Root沙箱**:
```python
# 可选：限制所有写入到指定目录树
HERMES_WRITE_SAFE_ROOT=/path/to/workspace
```

---

## 四、迭代模式总结

### 4.1 Hermes的迭代循环

```
┌────────────────────────────────────────────────────────────────┐
│                      Herme的自我迭代                            │
│                                                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐ │
│  │ 监控感知 │───▶│ 根因分析 │───▶│ 策略匹配 │───▶│ 执行验证 │ │
│  └──────────┘    └──────────┘    └──────────┘    └─────────┘ │
│       │                                                 │      │
│       └─────────────────────────────────────────────────┘      │
│                          反馈闭环                              │
└────────────────────────────────────────────────────────────────┘
```

### 4.2 关键迭代策略

| 策略 | 描述 | 实现 |
|------|------|------|
| **Skills持久化** | 将成功经验保存为skill | SKILL.md格式 |
| **主动纠错** | 低置信内容自动验证 | ProactiveKnowledgeCorrector |
| **意图预测** | 提前加载相关知识 | IntentPredictor |
| **自主修复** | 错误自动修复 | AutonomousRepairExecutor |
| **沙箱验证** | 执行前模拟验证 | SandboxExecutor |
| **阈值门控** | 低成功率升级人工 | 0.8阈值检查 |

### 4.3 记忆类型

| 类型 | 存储位置 | 用途 | TTL |
|------|----------|------|-----|
| **Session** | sessions/ | 当前会话上下文 | 会话内 |
| **Cross-session** | memories/ | 跨会话长期记忆 | 持久 |
| **Skills** | skills/ | 结构化知识 | 永久 |
| **Working** | RAM | 当前处理数据 | 临时 |

---

## 五、对MimirAether的启示

### 5.1 已有的能力

MimirAether已经有类似的架构：

1. **三环架构**: `mimicore/evolve/three_ring_architecture.py`
2. **自我进化**: `mimicore/evolve/self_evolution.py`
3. **文件操作**: `tools/file_operations.py`
4. **技能管理**: `tools/skill_manager_tool.py`

### 5.2 可借鉴的改进

1. **标准化学系格式**: 采用SKILL.md作为MimirAether的学习单元
2. **技能版本控制**: 对技能进行版本管理和更新检测
3. **沙箱执行**: 增强代码执行的沙箱验证
4. **意图预测预加载**: 基于历史预测用户意图

### 5.3 实现建议

```python
# 1. 定义标准Skill格式
class MimirSkill:
    name: str
    version: str
    description: str
    content: str  # 核心实现或prompt
    references: List[str]
    metadata: Dict[str, Any]

# 2. Skill注册表
class SkillRegistry:
    def register(self, skill: MimirSkill)
    def get(self, name: str) -> MimirSkill
    def search(self, query: str) -> List[MimirSkill]
    def evolve(self, name: str, new_version: MimirSkill)

# 3. 迭代触发器
class IterationTrigger:
    async def should_evolve(self, context) -> bool
    async def collect_feedback(self, context) -> Dict
    async def plan_evolution(self, feedback) -> EvolutionPlan
```

---

## 六、参考资料

1. Hermes Agent SKILL.md: `~/.hermes/skills/autonomous-ai-agents/hermes-agent/SKILL.md`
2. MimirAether进化模块: `mimicore/evolve/self_evolution.py`
3. 三环架构: `mimicore/evolve/three_ring_architecture.py`
4. 文件操作: `tools/file_operations.py`

---

_学习完成，继续探索中..._
