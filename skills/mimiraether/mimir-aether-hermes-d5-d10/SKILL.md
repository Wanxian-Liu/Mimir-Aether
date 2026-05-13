---
description: Hermes Agent核心源码系统学习 - 涵盖Day 5-12的platforms、gateway、cli、cron、agent、tools等模块的架构分析与集成参考
---

# Hermes Agent 源码学习 Phase 1 Days 5-10

## 概述

本技能记录对Hermes Agent核心源码模块的系统学习成果，适用于MimirAether的架构演进。

## 源码位置

```
~/.openclaw/projects/hermes-agent/
├── hermes_cli/        # CLI入口
├── gateway/           # 网关服务
│   └── platforms/     # 多平台适配器
├── cron/              # 定时任务
├── agent/             # 智能体核心
├── tools/             # 工具集
└── .env.example       # 环境变量模板
```

## Day 5: platforms/ 多平台接入

### 核心文件
- `hermes_cli/platforms.py` - 平台注册表
- `gateway/platforms/base.py` - 基类适配器
- `gateway/platforms/*.py` - 具体实现 (18个平台)

### 关键类

```python
# 消息事件 (MessageEvent)
@dataclass
class MessageEvent:
    text: str
    message_type: MessageType  # TEXT/PHOTO/AUDIO/VIDEO/DOCUMENT
    source: SessionSource
    media_urls: List[str]
    reply_to_message_id: str
    auto_skill: str

# 发送结果 (SendResult)
@dataclass
class SendResult:
    success: bool
    message_id: str
    error: str
    retryable: bool

# 基类 (BasePlatformAdapter)
class BasePlatformAdapter(ABC):
    async def connect() -> bool
    async def disconnect()
    async def send(chat_id, content, reply_to, metadata) -> SendResult
    async def send_image(chat_id, image_url, caption)
    async def send_voice(chat_id, audio_path)
    async def send_video(chat_id, video_path)
    async def send_document(chat_id, file_path)
    async def handle_message(event: MessageEvent)
```

### 平台列表
```
cli, telegram, discord, slack, whatsapp, signal, bluebubbles,
email, homeassistant, mattermost, matrix, dingtalk, feishu,
wecom, wecom_callback, weixin, webhook, api_server
```

## Day 6: gateway/ 服务化架构

### 核心文件
- `gateway/run.py` - 网关主入口 (~415KB)
- `gateway/config.py` - 配置管理 (~50KB)
- `gateway/session.py` - 会话管理
- `gateway/delivery.py` - 消息投递

### 启动流程
```python
# run.py
def start_gateway():
    config = load_gateway_config()
    adapters = _create_all_adapters(config)
    for adapter in adapters:
        asyncio.create_task(adapter.connect())
    GatewayRunner(adapters).run()
```

## Day 7: cli/ 命令行入口

### 命令结构
```
hermes chat                 # 交互式对话
hermes gateway [start|stop|status]
hermes setup               # 设置向导
hermes cron [list|status]
hermes doctor              # 诊断
hermes model               # 模型切换
hermes config              # 配置管理
hermes honcho [setup|mode]
```

### Profile机制
```python
# --profile/-p 切换配置
hermes --profile work chat
hermes --profile dev gateway start
```

## Day 8: cron/ 定时任务

### 核心文件
- `cron/scheduler.py` - 调度器 (~39KB)
- `cron/jobs.py` - 任务管理

### 投递目标
- `deliver="local"` - 仅本地保存
- `deliver="origin"` - 投递到来源
- `deliver="telegram:chat_id"` - 指定平台

### 执行流程
```
tick() → get_due_jobs() → _build_job_prompt()
      → run_agent() → _deliver_result()
```

## Day 9: env/ 环境配置

### 关键环境变量

**LLM Providers**:
```bash
OPENROUTER_API_KEY      # 默认
GOOGLE_API_KEY         # Gemini
KIMI_API_KEY           # Kimi/Moonshot
GLM_API_KEY            # Z.ai/GLM
```

**平台配置**:
```bash
TELEGRAM_BOT_TOKEN
DISCORD_BOT_TOKEN
SLACK_BOT_TOKEN
EMAIL_SMTP_HOST/PORT
```

**工具**:
```bash
EXA_API_KEY           # 网页搜索
FAL_KEY               # 图像生成
BROWSERBASE_API_KEY   # 浏览器自动化
```

### 加载优先级
1. `~/.openclaw/projects/MimirAether/.env` (override=True)
2. 项目 `.env` (override取决于步骤1)

## Day 10: 架构总览

### 模块依赖
```
hermes_cli → gateway → agent → cron → tools
```

### 设计模式
1. **适配器模式** - 统一接口适配多平台
2. **事件驱动** - MessageEvent + handle_message
3. **生命周期钩子** - on_processing_start/complete
4. **重试+降级** - _send_with_retry + 纯文本降级
5. **会话隔离** - SessionSource + 平台锁
6. **后台任务** - asyncio + 任务管理

## 差距分析与借鉴

### MimirAether需要借鉴
1. 多平台抽象 - 当前仅CLI
2. 会话管理 - SessionSource设计
3. 定时任务 - Cron调度完善
4. 流式处理 - SSE支持
5. 配置管理 - 多profile支持

### 可复用模块
1. `gateway/platforms/base.py` - 媒体缓存
2. `cron/scheduler.py` - 投递逻辑
3. `hermes_cli/env_loader.py` - 环境加载

---

**学习时间**: Phase 1 Days 5-10
**源码路径**: `~/.openclaw/projects/hermes-agent/`
**学习笔记**: `~/.openclaw/mimir-aether/memories/hermes-d5-d10-study.md`

---

## Day 11: agent/ 核心Agent逻辑

### 核心文件
- `run_agent.py` (~8000行) - AIAgent主类，核心对话循环
- `agent/__init__.py` - ContextEngine基类定义
- `agent/context_engine.py` - 上下文压缩引擎基类
- `agent/context_compressor.py` (~820行) - 默认压缩实现
- `agent/memory_manager.py` - 记忆管理器编排
- `agent/memory_provider.py` - 记忆提供者基类
- `agent/prompt_builder.py` (~1037行) - 系统提示构建
- `agent/smart_model_routing.py` - 智能模型路由
- `agent/auxiliary_client.py` (~2614行) - 辅助任务客户端

### AIAgent核心架构

```python
class AIAgent:
    # 核心属性
    model: str                    # 模型名称
    max_iterations: int = 90      # 最大工具调用迭代
    iteration_budget: IterationBudget  # 共享迭代预算
    platform: str                 # "cli", "telegram", etc.
    
    # 核心方法
    run_conversation(user_message, system_message, conversation_history)
    _build_system_prompt()         # 构建系统提示
    _api_call_with_retry()        # API调用+重试
    _handle_tool_calls()          # 工具调用处理
```

### ContextEngine 抽象基类

```python
class ContextEngine(ABC):
    # 必需属性
    name: str                     # 引擎标识符
    
    # Token状态（run_agent.py读取）
    last_prompt_tokens: int
    last_completion_tokens: int
    threshold_tokens: int
    context_length: int
    compression_count: int
    
    # 压缩参数
    threshold_percent: float = 0.75  # 75%时触发压缩
    protect_first_n: int = 3         # 保护前N条消息
    protect_last_n: int = 6          # 保护后N条消息
    
    # 核心方法
    update_from_response(usage)      # 更新token使用
    should_compress(prompt_tokens)    # 是否压缩
    compress(messages) -> List       # 执行压缩
    
    # 生命周期
    on_session_start(session_id)
    on_session_end(session_id, messages)
    on_session_reset()
```

### ContextCompressor 实现

```python
class ContextCompressor(ContextEngine):
    def compress(messages):
        # 1. 工具输出修剪（廉价预热）
        # 2. 保护头部消息（系统+前3条）
        # 3. 保护尾部消息（token预算）
        # 4. 用LLM总结中间消息
        # 5. 迭代更新（保留之前摘要）
```

**压缩模板结构**:
```
## Goal           - 用户目标
## Constraints    - 约束和偏好
## Progress       - Done/In Progress/Blocked
## Key Decisions  - 关键决策
## Resolved Qs   - 已回答的问题
## Pending Asks   - 待处理请求
## Relevant Files - 相关文件
## Remaining Work - 剩余工作
## Critical Context - 关键上下文
## Tools & Patterns - 工具使用模式
```

### MemoryManager 架构

```python
class MemoryManager:
    # 提供者注册（最多1个外部）
    def add_provider(provider: MemoryProvider)
    
    # 系统提示
    def build_system_prompt() -> str
    
    # 预取/同步
    def prefetch_all(query, session_id) -> str
    def sync_all(user_content, assistant_content, session_id)
    
    # 工具路由
    def get_all_tool_schemas() -> List
    def handle_tool_call(tool_name, args) -> str
    
    # 生命周期
    def on_turn_start(turn_number, message, **kwargs)
    def on_session_end(messages)
    def on_pre_compress(messages) -> str
```

### MemoryProvider 基类

```python
class MemoryProvider(ABC):
    name: str
    
    # 必需
    def is_available() -> bool
    def initialize(session_id, **kwargs)
    def get_tool_schemas() -> List[Dict]
    
    # 可选
    def system_prompt_block() -> str
    def prefetch(query, session_id) -> str
    def sync_turn(user, assistant, session_id)
    def handle_tool_call(tool_name, args) -> str
    def shutdown()
    
    # 生命周期钩子
    def on_turn_start(turn_number, message, **kwargs)
    def on_session_end(messages)
    def on_pre_compress(messages) -> str
    def on_delegation(task, result, **kwargs)
```

### Smart Model Routing

```python
def choose_cheap_model_route(user_message, routing_config):
    # 简单问题用廉价模型
    # 复杂关键词: debug, implement, refactor, analyze...
    
def resolve_turn_route(user_message, config, primary):
    # 解析本轮实际使用的模型/运行时
    # 返回: model, runtime, label, signature
```

### Prompt Builder 关键功能

```python
# 上下文威胁检测
_CONTEXT_THREAT_PATTERNS = [
    "ignore.*instructions",
    "do not tell the user",
    "disregard.*rules",
    # ... 注入检测
]

# 构建系统提示
build_skills_system_prompt()    # 技能索引
build_context_files_prompt()     # SOUL.md, AGENTS.md
build_environment_hints()        # 环境变量提示
load_soul_md()                  # 加载SOUL.md
```

### 关键设计模式

1. **上下文压力管理** - token跟踪+阈值压缩
2. **记忆提供者编排** - 单一管理器+多提供者
3. **迭代预算** - 线程安全预算共享
4. **智能路由** - 简单问题廉价模型
5. **上下文威胁检测** - 注入防护

---

**Day 11学习时间**: 2026-04-23
**源码路径**: `~/.openclaw/projects/hermes-agent/agent/`, `~/.openclaw/projects/hermes-agent/run_agent.py`

---

## Day 12: tools/registry.py - 工具注册表实现

### 核心文件
- `tools/registry.py` (~400行) - 工具注册表核心
- `model_tools.py` (~700行) - 工具发现与调度
- `toolsets.py` - 工具集解析

### ToolRegistry 架构

```python
class ToolRegistry:
    """单例注册表，收集工具schema+处理器"""
    _tools: Dict[str, ToolEntry]          # 工具名 → 条目
    _toolset_checks: Dict[str, Callable]  # 工具集 → 可用性检查
    
    # 注册
    def register(name, toolset, schema, handler, 
                 check_fn, requires_env, is_async, ...)
    
    # Schema获取
    def get_definitions(tool_names) -> List[dict]  # OpenAI格式
    
    # 调度
    def dispatch(name, args) -> str  # 执行工具处理器
    
    # 查询
    def get_all_tool_names() -> List[str]
    def get_schema(name) -> dict
    def get_toolset_for_tool(name) -> str
    def is_toolset_available(toolset) -> bool
```

### ToolEntry 数据结构

```python
class ToolEntry:
    __slots__ = (
        "name", "toolset", "schema", "handler",
        "check_fn", "requires_env", "is_async",
        "description", "emoji", "max_result_size_chars",
    )
```

### 工具注册模式

```python
# 每个工具模块在导入时注册
from tools.registry import registry, tool_error, tool_result

def _check():
    return os.getenv("API_KEY") is not None

def _handler(args):
    # 处理逻辑
    return tool_result(data={"result": "ok"})

registry.register(
    name="my_tool",
    toolset="my_tools",
    schema={
        "name": "my_tool",
        "description": "...",
        "parameters": {...}
    },
    handler=_handler,
    check_fn=_check,
    requires_env=["API_KEY"],
)
```

### 工具发现流程

```python
# model_tools.py
def _discover_tools():
    _modules = [
        "tools.web_tools",
        "tools.terminal_tool",
        "tools.file_tools",
        "tools.vision_tools",
        # ... 50+ 工具模块
    ]
    for mod_name in _modules:
        importlib.import_module(mod_name)  # 触发register()

# MCP工具发现
from tools.mcp_tool import discover_mcp_tools
discover_mcp_tools()

# 插件工具发现
from hermes_cli.plugins import discover_plugins
discover_plugins()
```

### 工具调度流程

```python
def handle_function_call(function_name, function_args, ...):
    # 1. 参数类型强制转换
    function_args = coerce_tool_args(function_name, function_args)
    
    # 2. 插件钩子检查
    if not skip_pre_tool_call_hook:
        block_message = get_pre_tool_call_block_message(...)
        if block_message:
            return tool_error(block_message)
    
    # 3. 工具特定参数
    kwargs = {}
    if function_name == "terminal":
        kwargs["task_id"] = task_id
    elif function_name in ("read_file", "search_files"):
        kwargs["session_id"] = session_id
    
    # 4. 注册表调度
    return registry.dispatch(function_name, function_args, **kwargs)
```

### 参数类型强制转换

```python
def coerce_tool_args(tool_name, args):
    """LLM常返回 "42" 而非 42，此函数修复"""
    schema = registry.get_schema(tool_name)
    for key, value in args.items():
        if not isinstance(value, str):
            continue
        expected = schema["parameters"]["properties"][key]["type"]
        if expected == "integer":
            args[key] = int(value)
        elif expected == "boolean":
            args[key] = value.lower() == "true"
```

### 异步桥接

```python
def _run_async(coro):
    """同步→异步桥接，处理事件循环"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop and loop.is_running():
        # 在异步上下文中，运行在线程池
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    
    # CLI路径：使用持久化事件循环
    tool_loop = _get_tool_loop()
    return tool_loop.run_until_complete(coro)
```

### 关键工具集

| 工具集 | 工具 |
|--------|------|
| file_tools | read_file, write_file, patch, search_files |
| terminal_tools | terminal |
| web_tools | web_search, web_extract |
| vision_tools | vision_analyze |
| browser_tools | browser_navigate, browser_snapshot, etc. |
| skills_tools | skills_list, skill_view, skill_manage |
| memory_tools | memory, session_search |
| moa_tools | mixture_of_agents |

---

**Day 12学习时间**: 2026-04-23
**源码路径**: `~/.openclaw/projects/hermes-agent/tools/registry.py`, `~/.openclaw/projects/hermes-agent/model_tools.py`

---

## Day 13: tools/目录下其他核心工具

### 核心工具概览

| 工具文件 | 功能 |
|----------|------|
| `skills_tool.py` | 技能列表和查看 |
| `skill_manager_tool.py` | 技能创建/编辑/删除 |
| `skills_hub.py` | 技能市场Hub (111KB) |
| `skills_guard.py` | 技能安全扫描 |
| `memory_tool.py` | 持久化记忆 (MEMORY.md/USER.md) |
| `delegate_tool.py` | 子Agent委托 (44KB) |
| `terminal_tool.py` | 终端执行 (74KB) |
| `file_tools.py` | 文件操作 (37KB) |
| `browser_tool.py` | 浏览器自动化 (93KB) |
| `web_tools.py` | 网页搜索/提取 (86KB) |

### Skills Tool 架构

```python
# 技能目录结构
~/.openclaw/projects/MimirAether/skills/
├── my-skill/
│   ├── SKILL.md           # 主指令（必需）
│   ├── references/        # 支持文档
│   ├── templates/         # 输出模板
│   └── assets/           # 资源文件
└── category/
    └── another-skill/
        └── SKILL.md

# SKILL.md格式 (YAML Frontmatter)
---
name: skill-name
description: Brief description
version: 1.0.0
platforms: [macos, linux]
prerequisites:
  env_vars: [API_KEY]
  commands: [curl, jq]
metadata:
  hermes:
    tags: [fine-tuning, llm]
---

# Skill Title
Full instructions...
```

### SkillManagerTool 能力

```python
# 技能管理操作
skill_manage(action, name, content, category, ...)

# action选项:
# - create: 创建新技能
# - edit: 替换SKILL.md内容（完全重写）
# - patch: 目标性find-and-replace
# - delete: 删除用户技能
# - write_file: 添加支持文件
# - remove_file: 删除支持文件
```

### Skills Guard 安全扫描

```python
# 信任等级
TRUSTED_REPOS = {"openai/skills", "anthropics/skills"}

INSTALL_POLICY = {
    "builtin":       ("allow", "allow", "allow"),     # safe, caution, dangerous
    "trusted":       ("allow", "allow", "block"),
    "community":    ("allow", "block", "block"),
    "agent-created": ("allow", "allow", "ask"),
}

# 威胁模式类别
THREAT_PATTERNS = [
    # 数据泄露: curl/wget带密钥
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET)',
     "env_exfil_curl", "critical", "exfiltration"),
    # 提示注入
    (r'ignore\s+previous\s+instructions',
     "prompt_injection", "high", "injection"),
    # 破坏性命令
    (r'rm\s+-rf\s+/(?:\*|[^/*]+)',
     "destructive_rm_root", "critical", "destructive"),
]
```

### Memory Tool 设计

```python
class MemoryStore:
    # 两个记忆存储
    memory_entries: List[str]  # MEMORY.md - 代理个人笔记
    user_entries: List[str]    # USER.md - 用户信息
    
    # 冻结快照模式
    _system_prompt_snapshot: Dict[str, str]  # 会话开始时捕获
    # 中间写入更新磁盘但不改变system_prompt
```

### Memory Content 扫描

```python
_MEMORY_THREAT_PATTERNS = [
    # 提示注入
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    # 数据泄露
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET)',
     "exfil_curl"),
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc)',
     "read_secrets"),
    # 持久化
    (r'authorized_keys', "ssh_backdoor"),
]
```

### Delegate Tool 子Agent架构

```python
# 子Agent阻塞列表
DELEGATE_BLOCKED_TOOLS = frozenset([
    "delegate_task",  # 禁止递归委托
    "clarify",        # 禁止用户交互
    "memory",         # 禁止写共享记忆
    "send_message",   # 禁止跨平台副作用
    "execute_code",   # 应推理而非写脚本
])

# 子Agent系统提示构建
def _build_child_system_prompt(goal, context, workspace_path):
    return f"""
You are a focused subagent working on a specific delegated task.
YOUR TASK: {goal}
CONTEXT: {context}
WORKSPACE PATH: {workspace_path}
...
"""
```

### Terminal Tool 环境选择

```python
# 环境选择 (TERMINAL_ENV)
TERMINAL_ENV="local"    # 本地执行（默认，最快）
TERMINAL_ENV="docker"    # Docker容器
TERMINAL_ENV="modal"     # Modal云沙箱

# 危险命令审批
DANGEROUS_COMMANDS = {
    "rm -rf", "dd", ":(){:|:&};:",  # 破坏性
    "chmod -R 777", "chown -R",      # 权限
    "curl/wget远程脚本执行",           # 网络
}
```

### File Tools 安全机制

```python
# 阻止的设备路径
_BLOCKED_DEVICE_PATHS = frozenset({
    "/dev/zero", "/dev/random",  # 无限输出
    "/dev/stdin", "/dev/tty",      # 阻塞输入
})

# 敏感路径前缀
_SENSITIVE_PATH_PREFIXES = (
    "/etc/", "/boot/", "/usr/lib/systemd/",
)

# 读取大小保护
_DEFAULT_MAX_READ_CHARS = 100_000  # 约25-35K tokens
```

### 关键设计模式

1. **渐进式披露** - skills_list只返回元数据，skill_view加载完整内容
2. **冻结快照** - system_prompt在会话开始时冻结，中途写入不改变
3. **安全扫描** - 所有外部技能经过威胁模式扫描
4. **子Agent隔离** - 独立上下文+受限工具集+工作区隔离
5. **文件锁** - 防止并发写入冲突

---

**Day 13学习时间**: 2026-04-23
**源码路径**: `~/.openclaw/projects/hermes-agent/tools/`

---

## Day 14: skills/目录 - 技能系统实现

### 技能目录结构

```
~/.openclaw/projects/MimirAether/skills/           # 本地技能目录
├── github/                 # 分类目录
│   ├── github-pr-workflow/
│   │   └── SKILL.md
│   └── github-auth/
├── software-development/
│   └── systematic-debugging/
│       └── SKILL.md
└── ...
```

### 技能文件格式

```markdown
---
name: skill-name
description: Brief description (max 1024 chars)
version: 1.0.0
platforms: [macos, linux]   # 可选：限制平台
prerequisites:
  env_vars: [API_KEY]
  commands: [curl, jq]
metadata:
  hermes:
    tags: [tag1, tag2]
    related_skills: [mimiraether-hermes-code-study, mimiraether-hermes-integration]
    requires_toolsets: [web, terminal]
    requires_tools: [web_search]
---

# Skill Title

Full instructions...
```

### 技能索引构建

```python
def build_skills_system_prompt(available_tools, available_toolsets) -> str:
    # 两层缓存:
    # 1. 进程内LRU字典 (keyed by skills_dir, tools, toolsets)
    # 2. 磁盘快照 (.skills_prompt_snapshot.json)
    
    # 扫描技能目录
    for skill_file in iter_skill_index_files(skills_dir, "SKILL.md"):
        is_compatible, frontmatter, desc = _parse_skill_file(skill_file)
        # 检查: 平台兼容性、禁用列表、条件匹配
        if compatible and not_disabled and matches_conditions:
            skills_by_category[category].append((name, desc))
```

### 技能条件匹配

```python
def _skill_should_show(conditions, available_tools, available_toolsets):
    # requires_toolsets: 至少一个工具集可用
    # fallback_for_toolsets: 工具集不可用时的备用
    # requires_tools: 至少一个工具可用
    # fallback_for_tools: 工具不可用时的备用
```

### Frontmatter解析

```python
def parse_frontmatter(content) -> Tuple[Dict, str]:
    # 解析YAML frontmatter
    # 返回: (frontmatter_dict, remaining_body)
    
def extract_skill_description(frontmatter) -> str:
    # 提取truncated描述
    
def extract_skill_conditions(frontmatter) -> Dict:
    # 提取条件激活字段
```

### 技能发现

```python
def iter_skill_index_files(skills_dir, filename):
    """遍历技能目录，yield匹配的路径"""
    for root, dirs, files in os.walk(skills_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_SKILL_DIRS]
        if filename in files:
            yield Path(root) / filename

EXCLUDED_SKILL_DIRS = frozenset((".git", ".github", ".hub"))
```

### 技能工具

```python
# skills_list: 返回元数据（token高效）
skills_list(category_filter=None, tags=None, limit=None)

# skill_view: 加载完整技能内容
skill_view(name, file_path=None)
```

### Skills Hub集成

```python
# 技能来源
SKILL_SOURCES = ["official", "github", "clawhub", "claude-marketplace", "lobehub"]

# 信任等级
TRUST_LEVELS = ["builtin", "trusted", "community"]

# 安装流程
1. download_skill(source, identifier)
2. scan_skill(quarantine_path) -> ScanResult
3. should_allow_install(scan_result) -> (allowed, reason)
4. install_skill(quarantine_path) -> target_path
```

### 系统提示中的技能索引

```python
# 构建格式
"""
## Skills (mandatory)
Before replying, scan the skills below. If a skill matches or is even partially relevant
to your task, you MUST load it with skill_view(name) and follow its instructions.

  github:
    - github-pr-workflow: Manage PRs with gh CLI
    - github-issues: Create and manage issues
    
  software-development:
    - systematic-debugging: 4-phase root cause investigation
    - test-driven-development: RED-GREEN-REFACTOR cycle
"""
```

### 关键设计模式

1. **渐进式披露** - skills_list返回元数据，skill_view加载完整内容
2. **两层缓存** - 进程内LRU + 磁盘快照
3. **外部技能目录** - config.yaml配置，只读扫描
4. **平台过滤** - 技能声明平台兼容性
5. **条件激活** - 基于可用工具/工具集显示技能

---

**Day 14学习时间**: 2026-04-23
**源码路径**: `~/.openclaw/projects/hermes-agent/agent/skill_utils.py`, `~/.openclaw/projects/hermes-agent/agent/prompt_builder.py`

---

## Phase 1 完成报告 (Days 1-15)

### 源码规模
- **总文件数**: 860个Python文件
- **总代码行数**: 390,092行
- **源码路径**: `~/.openclaw/projects/hermes-agent/`

---

### 模块架构总览

```
hermes-agent/
├── run_agent.py         (~8000行) - AIAgent核心类
├── cli.py               (~10000行) - CLI命令行入口
├── hermes_cli/         - CLI子命令
├── gateway/            - 网关服务 (~400KB)
│   ├── platforms/      - 18个平台适配器
│   ├── session.py      - 会话管理
│   └── delivery.py     - 消息投递
├── agent/             - Agent核心逻辑 (~16K行)
│   ├── context_engine.py - 上下文压缩基类
│   ├── context_compressor.py - 默认压缩实现
│   ├── memory_manager.py - 记忆管理器
│   ├── memory_provider.py - 记忆提供者基类
│   ├── prompt_builder.py - 系统提示构建
│   ├── smart_model_routing.py - 智能路由
│   └── auxiliary_client.py - 辅助任务客户端
├── tools/             - 工具集 (~40个工具)
│   ├── registry.py     - 工具注册表
│   ├── skills_tool.py  - 技能工具
│   ├── skill_manager_tool.py - 技能管理
│   ├── skills_hub.py   - 技能市场
│   ├── memory_tool.py  - 记忆工具
│   ├── delegate_tool.py - 子Agent委托
│   ├── terminal_tool.py - 终端执行
│   ├── file_tools.py   - 文件操作
│   └── browser_tool.py - 浏览器自动化
├── skills/           - 技能库 (~30个分类)
└── cron/             - 定时任务调度
```

---

### 核心设计模式

#### 1. 适配器模式 (Platform Pattern)
```python
class BasePlatformAdapter(ABC):
    async def connect() -> bool
    async def send(chat_id, content) -> SendResult
    async def handle_message(event: MessageEvent)
```
18个平台统一接口：cli, telegram, discord, slack, whatsapp, signal, email, etc.

#### 2. 事件驱动 (Event-Driven)
```python
@dataclass
class MessageEvent:
    text: str
    message_type: MessageType
    source: SessionSource
    auto_skill: str
```

#### 3. 工具注册表 (Tool Registry)
```python
class ToolRegistry:
    def register(name, toolset, schema, handler, check_fn)
    def dispatch(name, args) -> str
    def get_definitions(tool_names) -> List[dict]
```

#### 4. 记忆提供者 (Memory Provider)
```python
class MemoryProvider(ABC):
    def is_available() -> bool
    def initialize(session_id, **kwargs)
    def prefetch(query) -> str
    def sync_turn(user, assistant)
    def get_tool_schemas() -> List[Dict]
```

#### 5. 上下文引擎 (Context Engine)
```python
class ContextEngine(ABC):
    def update_from_response(usage)
    def should_compress(prompt_tokens) -> bool
    def compress(messages) -> List[Dict]
```

#### 6. 技能系统 (Skills System)
- 渐进式披露：skills_list返回元数据，skill_view加载完整内容
- 两层缓存：进程内LRU + 磁盘快照
- 外部技能目录支持

---

### 关键子系统

#### 会话管理
- SessionSource隔离不同平台
- SQLite持久化会话历史
- 系统提示快照缓存

#### 上下文压缩
- 工具输出修剪（廉价预热）
- 保护头部+尾部消息
- 结构化摘要模板（Goal/Progress/Decisions/Resolved/Pending）

#### 智能路由
- 简单问题→廉价模型
- 复杂关键词检测
- Provider自动回退

#### 安全机制
- 提示注入检测
- 技能安全扫描（skills_guard）
- 危险命令审批
- 敏感路径保护

#### 子Agent委托
- 独立上下文+工具集隔离
- 并发控制（max_concurrent_children）
- 深度限制（MAX_DEPTH=2）

---

### 关键差距分析 (MimirAether vs Hermes)

| 领域 | Hermes优势 | MimirAether现状 |
|------|-----------|-----------------|
| 多平台 | 18个平台适配器 | 仅CLI |
| 会话管理 | SQLite持久化+SessionSource | 基础会话 |
| 上下文 | 完整压缩系统+快照 | 简单截断 |
| 工具系统 | 40+工具+注册表 | 基础工具 |
| 技能系统 | Hub+索引+渐进披露 | 技能管理 |
| 记忆 | MemoryProvider+多后端 | MEMORY.md |
| 子Agent | 委托+隔离+并发 | 无 |
| 定时任务 | Cron调度器 | 无 |

---

### Phase 2 建议学习方向

1. **gateway/深入** - 多平台消息路由
2. **记忆系统扩展** - 多后端记忆提供者
3. **工具系统完善** - 工具注册+调度
4. **技能Hub集成** - 技能发现+安装
5. **子Agent架构** - 委托+隔离机制

---

**Phase 1完成时间**: 2026-04-23
**学习天数**: 15天 (Days 1-15)
**源码路径**: `~/.openclaw/projects/hermes-agent/`
