# MimirAether Gateway 架构分析报告

> Staff Engineer 分析 | 2026-04-27

---

## 1. hermes-agent Gateway 核心架构

### 1.1 模块概览

```
gateway/
├── run.py              (9003行) ⭐ 核心入口 - GatewayRunner
├── session.py          (1086行) - SessionStore + SessionContext
├── config.py           (1125行) - 配置管理
├── stream_consumer.py  (728行)  - 流式响应处理
├── hooks.py            (170行)  - 事件钩子系统
├── delivery.py         (256行)  - Cron输出路由
├── channel_directory.py (276行)  - 频道目录
├── status.py           (439行)  - 运行时状态
├── pairing.py          (309行)  - DM配对授权
├── mirror.py           (132行)  - 镜像模式
├── display_config.py    (187行)  - 显示配置
├── sticker_cache.py     (111行)  - 贴纸缓存
├── session_context.py   (128行)  - SessionContext数据类
├── restart.py          (20行)   - 重启支持
├── __init__.py         (35行)   - 公共API导出
└── platforms/
    ├── base.py         (82249行) - BasePlatformAdapter
    ├── telegram.py     (121289行)
    ├── discord.py      (128876行)
    ├── feishu.py       (164122行)
    ├── whatsapp.py     (41386行)
    └── ... (其他平台)
```

### 1.2 run.py - GatewayRunner 核心职责 (9003行)

**核心功能:**
1. **平台适配器生命周期管理** - 启动/停止/重连各平台适配器
2. **消息路由** - 接收平台消息 → 路由到Agent → 返回响应
3. **Agent实例缓存** - 为每个session缓存AIAgent实例以保留prompt缓存
4. **流式响应处理** - 与stream_consumer协同处理流式输出
5. **中断模式** - "interrupt"(默认)、"queue"、"passthrough"
6. **内存Flush** - Session重置前自动调用Agent保存记忆
7. **运行时状态** - 写入runtime_status.json供外部监控

**关键类:**
```python
class GatewayRunner:
    def __init__(self, config: Optional[GatewayConfig] = None):
        self.adapters: Dict[Platform, BasePlatformAdapter] = {}
        self.session_store: SessionStore  # 会话存储
        self.delivery_router: DeliveryRouter  # 投递路由
        self.hooks: HookRegistry  # 钩子系统
        self._running_agents: Dict[str, Any]  # 运行中的Agent
        self._agent_cache: Dict[str, tuple]  # Agent实例缓存(用于prompt缓存)
        self._session_model_overrides: Dict[str, Dict]  # Per-session模型覆盖
```

**消息处理流程:**
```
1. 平台Adapter收到消息
2. → SessionStore.get_or_create_session()
3. → 检查busy_input_mode (interrupt/queue/passthrough)
4. → 如果interrupt模式且有running agent → 终止旧agent
5. → 从_agent_cache获取或创建AIAgent
6. → AIAgent.process_message() (支持流式)
7. → stream_consumer处理流式响应
8. → 发送响应到平台
9. → 更新Agent缓存/会话状态
```

### 1.3 session.py - 会话管理核心 (1086行)

**SessionStore vs MimirAether SessionManager:**

| 特性 | hermes-agent | MimirAether (当前) |
|------|-------------|-------------------|
| 存储 | SQLite + JSONL fallback | 仅内存dict |
| 持久化 | ✅ 完整 | ❌ 无 |
| 重置策略 | daily/idle/both/none | 仅TTL |
| Session Key | 复杂规则(平台/聊天/线程/用户) | 仅(session_id, platform, chat_id) |
| 记忆Flush | ✅ Reset前自动调用 | ❌ 无 |
| Transcript | ✅ 完整保存 | ❌ 无 |
| Token统计 | ✅ 输入/输出/缓存 | ❌ 无 |
| 成本追踪 | ✅ USD估算 | ❌ 无 |

**关键类:**
```python
@dataclass
class SessionSource:
    platform: Platform
    chat_id: str
    chat_name: Optional[str]
    chat_type: str  # "dm", "group", "channel", "thread"
    user_id: Optional[str]
    user_name: Optional[str]
    thread_id: Optional[str]

class SessionEntry:
    session_key: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    origin: SessionSource
    display_name: str
    # Token统计
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    total_tokens: float
    estimated_cost_usd: float
    # 状态
    memory_flushed: bool
    suspended: bool

class SessionStore:
    def __init__(self, sessions_dir, config, has_active_processes_fn):
        # SQLite SessionDB + JSONL fallback
        self._db: Optional[SessionDB]
        self._entries: Dict[str, SessionEntry]
```

**Session Key生成规则:**
```python
def build_session_key(source: SessionSource, ...) -> str:
    # DM: agent:main:{platform}:dm:{chat_id}:{thread_id?}
    # Group: agent:main:{platform}:group:{chat_id}:{thread_id?}:{user_id?}
    # Thread: 默认共享session (thread_sessions_per_user=False)
```

### 1.4 config.py - 配置系统 (1125行)

**配置结构:**
```python
class Platform(Enum):
    LOCAL = "local"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    FEISHU = "feishu"
    WHATSAPP = "whatsapp"
    # ... 17个平台

@dataclass
class SessionResetPolicy:
    mode: str  # "daily", "idle", "both", "none"
    at_hour: int  # 每日重置小时(默认4)
    idle_minutes: int  # 空闲分钟(默认1440=24h)
    notify: bool  # 重置时通知
    notify_exclude_platforms: tuple  # 排除通知的平台

@dataclass
class PlatformConfig:
    enabled: bool
    token: Optional[str]
    api_key: Optional[str]
    home_channel: Optional[HomeChannel]
    # ... 还有很多平台特定配置

@dataclass
class GatewayConfig:
    platforms: Dict[Platform, PlatformConfig]
    sessions_dir: Path
    reset_policy: SessionResetPolicy
    # ...
```

### 1.5 stream_consumer.py - 流式响应处理 (728行)

**核心功能:**
1. **渐进式消息编辑** - 流式输出时定期edit消息更新内容
2. **Think块过滤** - 自动过滤 `<think>` `</think>` 等思考标签
3. **Flood Control** - 编辑失败时自适应退避
4. **分段处理** - 工具边界时创建新消息
5. ** Commentary 模式** - 临时注释消息
6. **Media占位符** - `MEDIA:<path>` 标签清理

**关键状态机:**
```python
class GatewayStreamConsumer:
    _queue: queue.Queue  # 文本片段队列
    _message_id: Optional[str]  # 当前编辑的消息ID
    _accumulated: str  # 累积文本
    _in_think_block: bool  # 是否在think块内
    _edit_supported: bool  # 是否支持编辑
    _flood_strikes: int  # 连续flood错误计数
    _current_edit_interval: float  # 自适应编辑间隔
```

### 1.6 hooks.py - 事件钩子系统 (170行)

**支持的事件:**
- `gateway:startup` - Gateway启动
- `session:start` - 新session创建
- `session:end` - Session结束
- `session:reset` - Session重置
- `agent:start` - Agent开始处理
- `agent:step` - Agent每轮迭代
- `agent:end` - Agent处理完成
- `command:*` - 任意命令(通配符)

**内置Hook:**
- `boot-md` - 启动时运行`~/.hermes/BOOT.md`

### 1.7 delivery.py - 投递路由 (256行)

**投递目标格式:**
```python
DeliveryTarget.parse("origin")  # 返回到消息来源
DeliveryTarget.parse("local")   # 保存到本地文件
DeliveryTarget.parse("telegram")  # Telegram home channel
DeliveryTarget.parse("telegram:123456")  # 指定chat
DeliveryTarget.parse("feishu:oc_xxx")  # 飞书指定会话
```

**关键逻辑:**
- Cron输出自动路由到配置的target
- 超长内容自动截断并保存完整输出到文件
- 支持多目标投递

### 1.8 channel_directory.py - 频道目录 (276行)

**功能:**
- 启动时构建各平台的频道/联系人列表
- 缓存到 `~/.hermes/channel_directory.json`
- 支持人类可读的频道名解析(如 `#engineering` → `SLACK_CHANNEL_ID`)
- Discord支持Guild限定名 (`GuildName/channel-name`)

---

## 2. Gateway与Channel Adapters关系

```
┌─────────────────────────────────────────────────────────────────┐
│                        GatewayRunner                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Adapters  │  │SessionStore  │  │  DeliveryRouter       │  │
│  │  Dict[Platform, BasePlatformAdapter]                       │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                     │              │
└─────────┼─────────────────┼─────────────────────┼──────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌─────────────────┐ ┌───────────────┐ ┌──────────────────────────┐
│ BasePlatform    │ │ SessionEntry  │ │ Cron Output / Responses  │
│ Adapter         │ │ (SQLite+JSON) │ │                          │
│ - send()        │ │               │ │                          │
│ - edit_message()│ │               │ │                          │
│ - receive()     │ │               │ │                          │
└────────┬────────┘ └───────────────┘ └──────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────┐
│                   Platform Adapters                            │
│  TelegramAdapter | DiscordAdapter | FeishuAdapter | ...        │
│  每个平台独立的SDK集成、Webhook处理、消息格式化                  │
└────────────────────────────────────────────────────────────────┘
```

**关键接口 (BasePlatformAdapter):**
```python
class BasePlatformAdapter(ABC):
    platform: Platform
    MAX_MESSAGE_LENGTH: int
    
    @abstractmethod
    async def send(chat_id: str, content: str, metadata: dict) -> SendResult
        """发送消息"""
    
    @abstractmethod
    async def edit_message(chat_id: str, message_id: str, content: str) -> SendResult
        """编辑消息"""
    
    @abstractmethod
    async def start_listening(self, webhook_url: str = None) -> None
        """开始监听消息"""
    
    async def get_pending_message(session_key: str) -> MessageEvent | None
        """获取待处理消息(用于interrupt模式)"""
```

---

## 3. 抄写障碍分析

### 3.1 OpenClaw已有功能

| hermes-agent功能 | OpenClaw对应 | 兼容性 |
|-----------------|-------------|--------|
| AIAgent实例缓存 | sessions_spawn/sessions_send | ⚠️ 需适配 |
| 流式输出 | 模型API原生支持 | ✅ 可用 |
| 会话存储 | MEMORY.md / SESSION-STATE.md | ⚠️ 架构不同 |
| 配置管理 | OpenClaw config系统 | ⚠️ 需适配 |
| 钩子系统 | Hooks扩展 | ✅ 可1:1实现 |
| Provider解析 | OpenClaw provider系统 | ❌ 完全重写 |

### 3.2 需完全重写的模块

| 模块 | 重写原因 | 工作量 |
|------|---------|--------|
| **run.py** | OpenClaw架构完全不同，无AIAgent类 | 🔴 极高 |
| **session.py** | hermes-agent用SQLite，MimirAether用内存dict | 🔴 高 |
| **stream_consumer.py** | OpenClaw消息模型不同 | 🟡 中 |
| **delivery.py** | OpenClaw无cron系统 | 🟡 中 |
| **channel_directory.py** | 依赖hermes sessions | 🟡 中 |

### 3.3 可1:1抄写的模块

| 模块 | 原因 | 工作量 |
|------|------|--------|
| **config.py** | 配置结构可复用 | 🟢 低 |
| **hooks.py** | 事件模式独立 | 🟢 低 |
| **pairing.py** | 配对逻辑独立 | 🟢 低 |
| **status.py** | 状态写入逻辑独立 | 🟢 低 |

### 3.4 自研改造点

1. **Agent调用方式** - hermes-agent直接实例化AIAgent，MimirAether需通过OpenClaw sessions
2. **流式输出** - 需适配OpenClaw的消息发送机制
3. **配置加载** - 复用OpenClaw的config系统
4. **Session存储** - 考虑复用OpenClaw的memory wiki

---

## 4. Gateway抄写计划

### 4.1 优先级排序

```
Phase 1: 基础框架 (1-2天)
├── 1. config.py 移植 (配置系统)
├── 2. hooks.py 移植 (事件钩子)
└── 3. 基础run.py框架 (GatewayRunner骨架)

Phase 2: 会话管理 (2-3天)
├── 4. session.py 重设计
├── 5. stream_consumer.py 适配
└── 6. pairing.py 移植

Phase 3: 投递和目录 (1-2天)
├── 7. delivery.py 移植
├── 8. channel_directory.py 移植
└── 9. status.py 移植

Phase 4: 集成和适配 (3-5天)
├── 10. run.py 完整实现
├── 11. OpenClaw sessions集成
└── 12. 端到端测试
```

### 4.2 依赖关系图

```
config.py ──────────────┐
                       │
hooks.py ───────────────┼──► run.py ◄─── (OpenClaw sessions)
                       │        │
status.py ──────────────┤        │
                       │        ▼
pairing.py ────────────┤   stream_consumer.py
                       │        │
session.py ────────────┤        │
                       │        ▼
delivery.py ───────────┤   channel_directory.py
                       │
platforms/base.py ─────┘
```

### 4.3 自研改造关键点

#### 4.3.1 Agent调用集成

**hermes-agent模式:**
```python
# run.py
agent = AIAgent(
    api_key=runtime["api_key"],
    base_url=runtime["base_url"],
    model=model,
    ...
)
response = await agent.process_message(user_message, session_ctx)
```

**MimirAether/OpenClaw模式:**
```python
# 需通过OpenClaw sessions API
result = sessions_send(session_key, message, timeoutSeconds=120)
# 或
spawn session with task, wait for completion
```

#### 4.3.2 流式输出适配

hermes-agent的流式输出通过自定义`AIAgent.streaming_callback`，MimirAether需要:
1. 接收OpenClaw的流式响应
2. 通过平台Adapter发送(可能需要adapter支持流式)

#### 4.3.3 Session存储策略

选项A: 复用hermes-agent的SQLite SessionDB
选项B: 使用OpenClaw memory wiki (MEMORY.md)
选项C: 混合 - SQLite存结构化数据，memory wiki存记忆

**推荐: 选项C**
- Session元数据(token统计等) → SQLite
- 用户记忆、偏好 → memory wiki
- 两者结合通过session_key关联

---

## 5. 关键设计决策

### 5.1 Gateway vs OpenClaw Session边界

**问题:** hermes-agent的GatewaySession 和 OpenClaw sessions 是两套并行的会话系统

**建议:**
- Gateway Session → 用于多平台消息路由和上下文
- OpenClaw Session → 用于AI推理和工具调用
- 两者通过 `session_key` 关联

### 5.2 流式响应的责任归属

**问题:** stream_consumer.py的逻辑应该放在哪里?

**选项A:** Gateway层处理
- 优点: 适配器只负责发送/编辑
- 缺点: Gateway复杂度增加

**选项B:** Adapter层处理
- 优点: 流式逻辑封装在平台内
- 缺点: 每个adapter重复实现

**推荐: 选项A (保留stream_consumer)**
- 统一流式处理逻辑
- 适配器保持简单

### 5.3 配置系统

**问题:** hermes-agent用`~/.hermes/config.yaml`，OpenClaw用`~/.openclaw/config.yaml`

**建议:**
- 短期: 独立`~/.openclaw/gateway_config.yaml`
- 长期: Gateway配置合并到OpenClaw主配置

---

## 6. 风险和注意事项

### 6.1 高风险项

1. **Agent缓存机制** - hermes-agent通过缓存AIAgent实例保留prompt缓存，OpenClaw sessions模式可能无法做到
2. **流式输出** - OpenClaw的流式输出机制与hermes-agent不同，需仔细适配
3. **SQLite依赖** - hermes-agent的SessionDB可能无法直接复用

### 6.2 中等风险项

1. **多平台适配器** - 每个平台的SDK差异大，需逐一适配
2. **中断模式** - "interrupt"模式需要能终止正在运行的agent
3. **内存Flush** - Session重置前的记忆保存需要能调用同一agent

### 6.3 低风险项

1. **hooks.py** - 完全独立，可直接抄写
2. **config.py** - 配置结构可复用
3. **pairing.py** - 配对逻辑独立

---

## 7. 下一步行动

### Senior Developer任务清单:

- [ ] **Task 1:** 创建`MimirAether/gateway/core/`目录，移植config.py
- [ ] **Task 2:** 移植hooks.py，测试事件触发机制
- [ ] **Task 3:** 设计MimirAether版session.py(基于SQLite+memory wiki混合)
- [ ] **Task 4:** 适配stream_consumer.py到OpenClaw消息模型
- [ ] **Task 5:** 移植delivery.py和channel_directory.py
- [ ] **Task 6:** 实现GatewayRunner核心框架
- [ ] **Task 7:** 集成OpenClaw sessions进行端到端测试
- [ ] **Task 8:** 飞书/Discord/Telegram适配器对接Gateway核心

---

*报告生成时间: 2026-04-27 10:30 GMT+8*
*分析者: Staff Engineer (Subagent)*
