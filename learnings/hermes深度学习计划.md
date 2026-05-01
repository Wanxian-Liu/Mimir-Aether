# Hermes Agent 源码深度学习计划

## 概述

本计划旨在系统化学习 Hermes Agent 源码，通过分步骤的深度分析，识别与 MimirAether 的差距，制定演进路线图。

**源码位置**: `/home/rayliu/.openclaw/projects/hermes-agent`

---

## 第一部分：核心模块分析

### 模块1：Agent核心循环 (agent_loop.py)
**文件**: `environments/agent_loop.py` (~750行)
**优先级**: P1

#### 1.1 架构概览
```
HermesAgentLoop
├── Async/await 事件驱动
├── OpenAI标准tool_calls协议
├── ThreadPoolExecutor (128 workers)
└── AgentResult 返回结构
```

#### 1.2 核心类分析

**HermesAgentLoop 类**
```python
class HermesAgentLoop:
    def __init__(self, server, tool_schemas, valid_tool_names, max_turns, ...)
    async def run(self, messages) -> AgentResult
```

**关键设计模式**:
- Async/await 异步模式
- OpenAI Tool Calls 标准协议
- Thread Pool 执行同步工具
- AgentResult dataclass 返回完整元数据

**AgentResult 结构**:
```python
@dataclass
class AgentResult:
    messages: List[Dict]           # 完整对话历史
    managed_state: Dict           # 托管状态
    turns_used: int               # LLM调用次数
    finished_naturally: bool      # 自然完成标志
    reasoning_per_turn: List      # 推理内容
    tool_errors: List[ToolError] # 工具错误记录
```

#### 1.3 学习目标
- [ ] 理解 async/await 在agent循环中的应用
- [ ] 掌握 OpenAI tool_calls 协议处理
- [ ] 理解 ThreadPoolExecutor 的配置与调优
- [ ] 分析工具调用分发机制

---

### 模块2：上下文压缩器 (context_compressor.py)
**文件**: `agent/context_compressor.py` (~900行)
**优先级**: P1

#### 2.1 压缩算法
```
1. 修剪旧工具输出（无LLM调用）
2. 保护头部消息（系统提示 + 首次交互）
3. 按token预算保护尾部消息
4. 用LLM总结中间轮次
5. 后续压缩时迭代更新摘要
```

#### 2.2 关键配置
```python
SUMMARY_PREFIX = "[CONTEXT COMPACTION — REFERENCE ONLY]..."
_MIN_SUMMARY_TOKENS = 2000
_SUMMARY_RATIO = 0.20           # 摘要占压缩内容的比例
_SUMMARY_TOKENS_CEILING = 12000
_SUMMARY_FAILURE_COOLDOWN_SECONDS = 600
```

#### 2.3 ContextEngine 基类
```python
class ContextEngine:
    def __init__(self, model, threshold_percent, ...)
    def should_compress(self, messages) -> bool
    def compress(self, messages, focus_topic) -> List[Dict]
    def on_session_reset(self) -> None
    def update_model(self, model, context_length, ...) -> None
```

#### 2.4 学习目标
- [ ] 理解上下文窗口管理策略
- [ ] 掌握摘要提示词设计
- [ ] 分析迭代摘要更新机制
- [ ] 理解失败冷却机制

---

### 模块3：提示词构建器 (prompt_builder.py)
**文件**: `agent/prompt_builder.py` (~1300行)
**优先级**: P1

#### 3.1 核心功能
```
1. 身份定义 (identity)
2. 平台提示 (platform hints)
3. 技能索引 (skills index)
4. 上下文文件 (context files)
5. 安全扫描 (injection detection)
```

#### 3.2 安全机制
```python
_CONTEXT_THREAT_PATTERNS = [
    "prompt_injection",
    "deception_hide",
    "sys_prompt_override",
    "disregard_rules",
    "bypass_restrictions",
    ...
]
```

#### 3.3 学习目标
- [ ] 理解系统提示的模块化组装
- [ ] 掌握上下文文件发现机制
- [ ] 分析提示注入检测逻辑
- [ ] 理解技能匹配条件

---

### 模块4：工具注册与分发 (model_tools.py + registry.py)
**文件**: `model_tools.py` (~600行), `tools/registry.py` (~500行)
**优先级**: P1

#### 4.1 架构设计
```
工具文件 (tools/*.py)
    ↓ registry.register()
工具注册表 (ToolRegistry)
    ↓ get_definitions()
model_tools.py
    ↓ handle_function_call()
实际工具执行
```

#### 4.2 异步桥接
```python
def _run_async(coro):
    # 单例事件循环，避免 "Event loop is closed" 错误
    # 支持主线程、工作线程、不同场景
```

#### 4.3 ToolRegistry 类
```python
class ToolRegistry:
    def register(self, name, toolset, schema, handler, check_fn, ...)
    def get_definitions(self, tool_names, quiet) -> List[dict]
    def dispatch(self, name, args, **kwargs) -> str
```

#### 4.4 学习目标
- [ ] 理解自注册架构
- [ ] 掌握工具可用性检查机制
- [ ] 分析异步执行策略
- [ ] 理解工具到工具集的映射

---

### 模块5：状态管理 (hermes_state.py)
**文件**: `hermes_state.py` (~1400行)
**优先级**: P2

#### 5.1 数据库设计
```
sessions 表
├── id, source, user_id, model
├── started_at, ended_at, end_reason
├── message_count, tool_call_count
├── input_tokens, output_tokens
├── estimated_cost_usd, actual_cost_usd
└── parent_session_id (压缩触发会话分裂)

messages 表
├── session_id, role, content
├── tool_call_id, tool_calls, tool_name
├── timestamp, token_count
└── reasoning, reasoning_details

FTS5 虚拟表 (全文搜索)
```

#### 5.2 关键特性
- WAL 模式 (并发读写)
- FTS5 全文搜索
- 随机退避重试 (写竞争优化)
- 会话压缩分裂 (parent_session_id 链)

#### 5.3 学习目标
- [ ] 理解 SQLite WAL 模式
- [ ] 掌握 FTS5 全文搜索
- [ ] 分析会话生命周期管理
- [ ] 理解成本追踪机制

---

### 模块6：网关系统 (gateway/)
**文件**: `gateway/run.py` (~10000行), `gateway/session.py` (~1200行)
**优先级**: P2

#### 6.1 核心组件
```
gateway/
├── run.py           # 主网关循环
├── session.py       # 会话管理
├── config.py        # 配置管理
├── channel_directory.py  # 渠道目录
├── delivery.py      # 消息投递
├── hooks.py         # 钩子系统
└── platforms/       # 平台适配器
```

#### 6.2 架构特点
- 多平台支持 (Telegram, Discord, CLI, etc.)
- Webhook 事件驱动
- 消息投递确认
- 配对系统

#### 6.3 学习目标
- [ ] 理解网关架构设计
- [ ] 掌握会话上下文管理
- [ ] 分析平台适配器模式
- [ ] 理解消息投递机制

---

### 模块7：定时任务系统 (cron/)
**文件**: `cron/scheduler.py` (~1000行), `cron/jobs.py` (~800行)
**优先级**: P3

#### 7.1 核心组件
```
cron/
├── scheduler.py     # 调度器
└── jobs.py          # 任务定义
```

#### 7.2 调度模式
- Cron 表达式支持
- 一次性任务
- 周期性任务
- 事件触发任务

#### 7.3 学习目标
- [ ] 理解调度器实现
- [ ] 掌握任务定义格式
- [ ] 分析持久化策略

---

### 模块8：CLI系统 (hermes_cli/)
**文件**: `hermes_cli/` 目录
**优先级**: P3

#### 8.1 核心组件
```
hermes_cli/
├── claw.py          # CLI主入口
├── models.py        # 模型管理
├── profiles.py      # 配置管理
├── platforms.py     # 平台配置
├── cron.py          # 定时任务CLI
├── auth.py          # 认证
└── plugins.py      # 插件系统
```

#### 8.2 学习目标
- [ ] 理解CLI架构
- [ ] 掌握配置管理
- [ ] 分析认证流程

---

## 第二部分：设计模式总结

### 1. 异步驱动模式
```python
# Hermes 使用 async/await 作为核心执行模型
async def run(self, messages) -> AgentResult:
    for turn in range(max_turns):
        response = await self.server.chat_completion(...)
        if response.choices[0].message.tool_calls:
            results = await self._execute_tools(...)
```

### 2. 自注册模式
```python
# 工具模块级别注册
# tools/terminal_tool.py
from tools.registry import registry
registry.register(
    name="terminal",
    toolset="core",
    schema={...},
    handler=terminal_handler,
)
```

### 3. 配置驱动模式
```python
# YAML配置 + 代码默认值
# cli-config.yaml.example
model: gpt-4o
temperature: 0.7
max_turns: 30
```

### 4. 上下文压缩模式
```python
# 保护头尾，压缩中间
def compress(self, messages):
    head = protect_head(messages, n=3)
    tail = protect_tail_by_tokens(messages, budget=20000)
    summary = await summarize_middle(head, tail)
    return head + [summary] + tail
```

### 5. 单例+线程本地模式
```python
# 事件循环管理
_tool_loop = None  # 主线程单例
_worker_thread_local = threading.local()  # 工作线程本地
```

---

## 第三部分：MimirAether 对比分析

### 对比表

| 功能 | Hermes | MimirAether | 差距 |
|------|--------|-------------|------|
| Agent Loop | HermesAgentLoop | 待确认 | 待分析 |
| 上下文压缩 | ContextCompressor | 待确认 | 待分析 |
| 工具注册 | ToolRegistry | 待确认 | 待分析 |
| 状态存储 | SQLite + WAL | 待确认 | 待分析 |
| 网关 | 多平台网关 | 待确认 | 待分析 |
| 调度 | CronScheduler | 待确认 | 待分析 |

---

## 第四部分：分步骤学习计划

### Week 1: 基础设施 (Day 1-7)

**Day 1: 项目结构探索**
- [ ] 浏览完整目录结构
- [ ] 理解各目录职责
- [ ] 阅读 README.md
- [ ] 阅读 AGENTS.md

**Day 2-3: 工具系统 (model_tools + registry)**
- [ ] 精读 `model_tools.py`
- [ ] 精读 `tools/registry.py`
- [ ] 分析工具注册流程
- [ ] 验证：运行工具发现机制

**Day 4-5: 状态管理 (hermes_state)**
- [ ] 精读 `hermes_state.py`
- [ ] 分析 SQLite Schema
- [ ] 理解 FTS5 搜索
- [ ] 验证：创建测试数据库

**Day 6-7: 核心常量 (hermes_constants)**
- [ ] 精读 `hermes_constants.py`
- [ ] 理解路径配置
- [ ] 分析常量组织

### Week 2: Agent核心 (Day 8-14)

**Day 8-9: Agent循环 (agent_loop)**
- [ ] 精读 `environments/agent_loop.py`
- [ ] 分析 HermesAgentLoop 类
- [ ] 理解 tool_calls 处理
- [ ] 验证：单轮对话测试

**Day 10-11: 上下文压缩 (context_compressor)**
- [ ] 精读 `agent/context_compressor.py`
- [ ] 分析压缩算法
- [ ] 理解摘要策略
- [ ] 验证：触发压缩测试

**Day 12-14: 提示词构建 (prompt_builder)**
- [ ] 精读 `agent/prompt_builder.py`
- [ ] 分析安全扫描
- [ ] 理解技能索引
- [ ] 验证：提示词组装测试

### Week 3: 高级模块 (Day 15-21)

**Day 15-17: 网关系统 (gateway)**
- [ ] 精读 `gateway/run.py`
- [ ] 精读 `gateway/session.py`
- [ ] 分析会话管理
- [ ] 理解多平台架构

**Day 18-19: 定时任务 (cron)**
- [ ] 精读 `cron/scheduler.py`
- [ ] 精读 `cron/jobs.py`
- [ ] 分析调度机制

**Day 20-21: CLI系统 (hermes_cli)**
- [ ] 浏览 `hermes_cli/` 目录
- [ ] 理解命令架构
- [ ] 分析配置管理

### Week 4: 深入实践 (Day 22-28)

**Day 22-24: 工具开发**
- [ ] 分析现有工具结构
- [ ] 理解工具定义格式
- [ ] 验证：添加简单工具

**Day 25-26: 集成测试**
- [ ] 运行完整对话测试
- [ ] 触发上下文压缩
- [ ] 验证状态持久化

**Day 27-28: 对比分析**
- [ ] 对比 MimirAether 实现
- [ ] 识别功能差距
- [ ] 制定演进计划

---

## 第五部分：输出模板

### 学习日志模板

```markdown
## Day X: [主题]

### 阅读内容
- 文件1: 行范围
- 文件2: 行范围

### 关键发现
1. [发现1]
2. [发现2]
3. [发现3]

### 设计模式
- 模式1: 描述
- 模式2: 描述

### MimirAether对比
| 功能 | Hermes | MimirAether | 差距 |
|------|--------|-------------|------|
| ... | ... | ... | ... |

### 问题与思考
- Q1: ...
- A1: ...

### 验证实验
```python
# 实验代码
```
```

---

## 第六部分：验证清单

### 理解验证
- [ ] 能画出核心模块关系图
- [ ] 能解释异步执行流程
- [ ] 能描述工具注册机制
- [ ] 能说明上下文压缩算法

### 代码验证
- [ ] 能运行单轮对话
- [ ] 能触发上下文压缩
- [ ] 能添加新工具
- [ ] 能查询状态数据库

### 对比验证
- [ ] 能列出 Hermes 优势
- [ ] 能识别 MimirAether 差距
- [ ] 能制定演进路线

---

## 附录

### 关键文件索引

| 模块 | 文件 | 行数 | 优先级 |
|------|------|------|--------|
| Agent Loop | environments/agent_loop.py | ~750 | P1 |
| 上下文压缩 | agent/context_compressor.py | ~900 | P1 |
| 提示词构建 | agent/prompt_builder.py | ~1300 | P1 |
| 模型工具 | model_tools.py | ~600 | P1 |
| 工具注册 | tools/registry.py | ~500 | P1 |
| 状态存储 | hermes_state.py | ~1400 | P2 |
| 网关 | gateway/run.py | ~10000 | P2 |
| 会话 | gateway/session.py | ~1200 | P2 |
| 调度 | cron/scheduler.py | ~1000 | P3 |
| CLI | hermes_cli/ | ~3000 | P3 |

### 参考资料
- Hermes README.md
- Hermes AGENTS.md
- OpenAI Tool Calls 文档
- SQLite WAL 模式文档
- Python asyncio 最佳实践
