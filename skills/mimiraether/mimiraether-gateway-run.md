# Gateway Run 模块技能文档

## 模块概览

**文件**: `gateway/run.py`
**核心类**: `GatewayRunner`

GatewayRunner是Hermes Agent消息网关的主控制器，负责：
- 管理所有平台适配器的生命周期
- 将消息路由到AI Agent
- 处理Agent的创建、缓存、中断
- 处理用户授权和会话管理

---

## 核心架构

### 1. 平台适配器管理

```
GatewayRunner
├── adapters: Dict[Platform, BasePlatformAdapter]
├── delivery_router: DeliveryRouter
├── session_store: SessionStore
└── _failed_platforms: Dict[Platform, Dict]  # 重连队列
```

**支持的平台**:
- Telegram, Discord, WhatsApp, Slack, Signal
- HomeAssistant, Email, SMS
- DingTalk, Feishu, WeCom, Weixin
- Mattermost, Matrix, BlueBubbles
- API Server, Webhook

**平台适配器工厂**:
```python
def _create_adapter(self, platform: Platform, config: Any) -> Optional[BasePlatformAdapter]:
    if platform == Platform.TELEGRAM:
        return TelegramAdapter(config)
    elif platform == Platform.DISCORD:
        return DiscordAdapter(config)
    # ... 其他平台
```

### 2. 消息处理流程

```
MessageEvent
    ↓
_handle_message()
    ├── 1. 授权检查 (_is_user_authorized)
    ├── 2. 命令拦截 (/new, /reset, /stop 等)
    ├── 3. Agent运行检测 → 中断或排队
    ├── 4. 会话获取 (session_store.get_or_create_session)
    ├── 5. 消息预处理 (Vision, STT, 媒体处理)
    └── 6. Agent运行 (_handle_message_with_agent)
```

### 3. Agent生命周期管理

```python
# Agent缓存 (保持prompt缓存效果)
self._agent_cache: Dict[str, tuple]  # (AIAgent, config_signature)

# 运行中的Agent (用于中断)
self._running_agents: Dict[str, Any]
self._running_agents_ts: Dict[str, float]  # 开始时间戳

# Pending哨兵 (防止异步期间重复创建)
_AGENT_PENDING_SENTINEL = object()
```

**关键流程**:
1. 进入消息处理前设置哨兵
2. 创建Agent并替换哨兵
3. 运行Agent
4. 清理资源

### 4. 授权系统

```python
def _is_user_authorized(self, source: SessionSource) -> bool:
    # 1. HA/Webhook自动授权
    if source.platform in (Platform.HOMEASSISTANT, Platform.WEBHOOK):
        return True
    
    # 2. 配对存储检查
    if self.pairing_store.is_approved(platform_name, user_id):
        return True
    
    # 3. 环境变量白名单
    platform_allowlist = os.getenv("TELEGRAM_ALLOWED_USERS", "")
    global_allowlist = os.getenv("GATEWAY_ALLOWED_USERS", "")
    
    # 4. 全局允许
    if os.getenv("GATEWAY_ALLOW_ALL_USERS") == "true":
        return True
```

### 5. 命令分发

**内置命令**:
- `/new`, `/reset` - 新会话
- `/stop` - 停止当前Agent
- `/restart` - 重启网关
- `/model` - 切换模型
- `/compress` - 压缩上下文
- `/background` - 后台任务
- `/voice` - 语音模式
- `/retry`, `/undo` - 重试/撤销
- `/plan` - 计划模式

**命令解析流程**:
```python
# 别名解析
_cmd_def = _resolve_cmd(command)
canonical = _cmd_def.name if _cmd_def else command

# 技能命令 (/skill-name)
if cmd_key := resolve_skill_command_key(command):
    event.text = build_skill_invocation_message(cmd_key, args)

# 快速命令 (config.yaml定义)
if command in quick_commands:
    if qcmd.get("type") == "exec":
        # 执行shell命令
    elif qcmd.get("type") == "alias":
        # 命令别名
```

### 6. 后台任务

#### 6.1 平台重连监听器
```python
async def _platform_reconnect_watcher(self):
    # 指数退避: 30s → 60s → 120s → 240s → 300s (上限)
    # 最多20次重试
```

#### 6.2 会话过期监听器
```python
async def _session_expiry_watcher(self):
    # 每5分钟检查过期会话
    # 自动刷新内存后再重置
    # 防止用户下次消息时阻塞
```

#### 6.3 进程恢复监听器
```python
# 崩溃恢复 - 重建检查点中的后台进程
process_registry.recover_from_checkpoint()
```

### 7. 优雅关闭

```python
async def stop(self, *, restart: bool = False, ...):
    # 1. 标记draining状态
    # 2. 等待活跃Agent完成 (最多restart_drain_timeout)
    # 3. 中断剩余Agent
    # 4. 断开所有平台适配器
    # 5. 清理工具资源 (终端、浏览器、进程)
    # 6. 写入clean_shutdown标记
```

---

## 与MimirAether的集成要点

### 1. 会话键生成

```python
# 与Hermes相同的session key生成逻辑
session_key = build_session_key(source)
# 格式: agent:main:{platform}:{chat_type}:{chat_id}:{thread_id}:{user_id}
```

### 2. 消息处理集成

如果MimirAether需要处理来自网关的消息：
```python
# 1. 实现BasePlatformAdapter接口
class MyAdapter(BasePlatformAdapter):
    platform = Platform.MY_PLATFORM
    async def connect(self) -> bool: ...
    async def send(self, chat_id, content, **kwargs) -> SendResult: ...
    async def disconnect(self): ...

# 2. 注册到GatewayRunner
runner = GatewayRunner(config)
runner.adapters[Platform.MY_PLATFORM] = MyAdapter(config)
```

### 3. 事件钩子系统

```python
# 监听钩子
await self.hooks.emit("gateway:startup", {"platforms": [...]})
await self.hooks.emit("command:/new", {"user_id": "...", "args": "..."})

# 可用钩子:
# - gateway:startup, gateway:shutdown
# - command:{name}
# - on_session_finalize
```

### 4. 流式响应处理

使用StreamConsumer进行流式消息编辑：
```python
consumer = GatewayStreamConsumer(
    adapter=my_adapter,
    chat_id=chat_id,
    config=StreamConsumerConfig(
        cursor=" ✍️",  # 编辑时显示的光标
        edit_interval=1.0,  # 编辑间隔(秒)
    )
)

# Agent流式回调
consumer.on_delta(text)  # 添加文本
consumer.on_segment_break()  # 新消息段
consumer.finish()  # 完成

# 在async任务中运行
await consumer.run()
```

---

## 关键设计模式

### 1. 哨兵模式防止重复Agent创建

```python
# 在第一个await前设置哨兵
self._running_agents[_quick_key] = _AGENT_PENDING_SENTINEL

try:
    return await self._handle_message_with_agent(event, source, _quick_key)
finally:
    # 确保异常时清理哨兵
    if self._running_agents.get(_quick_key) is _AGENT_PENDING_SENTINEL:
        del self._running_agents[_quick_key]
```

### 2. 配置桥接

```python
# config.yaml → 环境变量 → Agent运行时
# 示例: agent.gateway_timeout → HERMES_AGENT_TIMEOUT
```

### 3. 渐进式功能检测

```python
# 平台适配器检查可选依赖
def check_telegram_requirements():
    try:
        import telegram
        return True
    except ImportError:
        return False
```

---

## 配置示例

```yaml
# ~/.hermes/config.yaml
agent:
  max_turns: 100
  gateway_timeout: 1800
  restart_drain_timeout: 30
  reasoning_effort: medium
  
display:
  busy_input_mode: interrupt  # interrupt | queue
  show_reasoning: false
  background_process_notifications: all

model:
  default: claude-sonnet-4-20250514

platforms:
  telegram:
    enabled: true
    bot_token: ${TELEGRAM_BOT_TOKEN}
```

---

## 参考资料

- `gateway/platforms/base.py` - 平台适配器基类
- `gateway/session.py` - 会话管理
- `gateway/stream_consumer.py` - 流式响应处理
- `agent/skill_commands.py` - 技能命令系统
