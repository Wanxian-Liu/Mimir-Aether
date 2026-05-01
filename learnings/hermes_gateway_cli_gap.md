# Hermes vs MimirAether: Gateway & CLI 架构对比

> 学习日期: 2026-04-30  
> Hermes: gateway/run.py (9003行) + cron/ + hermes_cli/  
> MimirAether: api_service.py (436行) + cron/ + cli.py  

---

## 1. Hermes 设计亮点 (Top 5)

### 亮点1: GatewayRunner 统一生命周期 (~9000行单一文件)

GatewayRunner 管理所有平台适配器、会话存储、Agent缓存、Cron ticker、
信号处理、优雅draining和重启。虽大但职责明确：

```python
class GatewayRunner:
    def __init__(self):
        self.adapters: Dict[Platform, BasePlatformAdapter]
        self.session_store: SessionStore
        self.delivery_router: DeliveryRouter
        self._running_agents: Dict[str, AIAgent]
        self._agent_cache: Dict[str, tuple]
        self._failed_platforms: Dict[Platform, dict]  # 后台重连队列
        self.hooks: HookRegistry
        self._session_db: SessionDB
```

关键生命周期：
1. `start()` → 连接所有平台适配器 → 恢复进程 → 暂停残留会话
2. `wait_for_shutdown()` → 信号处理 → drain活跃agent → cron停止
3. 支持 SIGUSR1 重启、SIGINT/SIGTERM 优雅关闭

### 亮点2: 多平台适配器统一接口 (20+平台)

BasePlatformAdapter 定义了标准接口：

```python
class BasePlatformAdapter:
    async def connect() -> bool
    async def disconnect()
    async def send(chat_id, content, metadata) -> SendResult
    def set_message_handler(handler)
    def set_fatal_error_handler(handler)
    @staticmethod extract_media(content) -> (media_files, cleaned)
```

支持的平台：telegram, discord, slack, whatsapp, signal, matrix,
mattermost, homeassistant, dingtalk, feishu, wecom, wecom_callback,
weixin, sms, email, webhook, bluebubbles

路由时优先使用 live adapter (支持E2EE)，fallback 到 standalone HTTP。

### 亮点3: Cron 系统深度集成

三层架构：
- `cron/jobs.py` — CRUD + schedule 解析 (interval/cron/once)
- `cron/scheduler.py` — tick() + run_job() + deliver_result()
- `gateway/run.py:_start_cron_ticker()` — 后台线程每60秒 tick

特性：
- 文件锁 (.tick.lock) 防止多进程重复执行
- Pre-run scripts 数据采集（路径遍历防护）
- Skills 注入到 cron prompt
- SILENT 标记抑制无更新时的交付
- 输出自动交付到 origin chat 或指定平台
- 频道目录每5分钟刷新 + 缓存每小时清理

### 亮点4: 配置系统多层桥接

加载顺序：config.yaml → .env 桥接 → os.environ

关键桥接代码：
```python
# config.yaml → TERMINAL_* env vars
for cfg_key, env_var in _terminal_env_map.items():
    if cfg_key in _terminal_cfg:
        os.environ[env_var] = str(_terminal_cfg[cfg_key])
```

支持：terminal, auxiliary(vision/web_extract/approval), agent,
display, timezone, security, network, compression 等配置段。

### 亮点5: CLI 使用 argparse subparsers + 命令函数分发

```python
subparsers = parser.add_subparsers(dest="command")
chat_parser = subparsers.add_parser("chat")
chat_parser.set_defaults(func=cmd_chat)

model_parser = subparsers.add_parser("model")
model_parser.set_defaults(func=cmd_model)
```

每个子命令有独立参数解析，`args.func(args)` 分发。比 MimirAether
的手工 if/elif/else 链式分发可维护性高得多。

---

## 2. MimirAether 差距列表 (P0-P3)

### P0: 阻塞级 — 核心架构缺失

| # | 差距 | 严重度 |
|---|------|--------|
| P0-1 | api_service.py 直接 aiohttp.web，无平台适配器层 | 🔴 |
| P0-2 | cron/scheduler.py 是空壳stub，tick()未定义 | 🔴 |
| P0-3 | CLI 使用 if/elif 手动命令分发，非 argparse subparsers | 🔴 |
| P0-4 | 无 GatewayRunner 生命周期管理 | 🔴 |

### P1: 关键级 — 功能性缺失

| # | 差距 | 严重度 |
|---|------|--------|
| P1-1 | 无 config.yaml 统一配置文件 | 🟠 |
| P1-2 | 无 BasePlatformAdapter 架构 | 🟠 |
| P1-3 | 无 Cron 与 Gateway 集成（后台线程 ticker） | 🟠 |
| P1-4 | 无 Agent 缓存（每次消息重建，浪费 prefix cache） | 🟠 |

### P2: 改进级 — 体验缺失

| # | 差距 | 严重度 |
|---|------|--------|
| P2-1 | 无会话存储和恢复 (SessionStore) | 🟡 |
| P2-2 | 无 Job 脚本支持 (pre-run scripts) | 🟡 |
| P2-3 | 无文件锁防 cron 重复执行 | 🟡 |
| P2-4 | 无 cron 输出自动交付到消息平台 | 🟡 |

### P3: 完善级 — 运维能力缺失

| # | 差距 | 严重度 |
|---|------|--------|
| P3-1 | 无 SIGUSR1 重启信号处理 | 🟢 |
| P3-2 | 无 PID 文件 / 运行状态文件管理 | 🟢 |
| P3-3 | 无 platform 重连队列 (failed_platforms) | 🟢 |
| P3-4 | 无 graceful draining (活跃agent等待) | 🟢 |

---

## 3. 修复建议 (分块写入)

### P0-1: api_service.py → GatewayRunner 架构

**修复块1**: 创建 gateway/runner.py
```
# gateway/runner.py
class GatewayRunner:
    def __init__(self, config):
        self.adapters = {}
        self.session_store = SessionStore(...)
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    async def start(self) -> bool:
        for platform, pconfig in self.config.platforms.items():
            adapter = self._create_adapter(platform, pconfig)
            adapter.set_message_handler(self._handle_message)
            await adapter.connect()
            self.adapters[platform] = adapter
        return len(self.adapters) > 0
```

**修复块2**: 创建 gateway/platforms/base.py
```
class BasePlatformAdapter:
    async def connect(self) -> bool: ...
    async def disconnect(self): ...
    async def send(self, chat_id, content, metadata=None): ...
    def set_message_handler(self, handler): ...
```

**修复块3**: api_service.py 改为 GatewayRunner 的子入口
```
# 旧: web.run_app(app) 直接启动
# 新: runner = GatewayRunner(config); await runner.start()
# HTTP API 作为 LOCAL 平台适配器实现
```

### P0-2: cron/scheduler.py 补全 tick()

**修复块1**: 在 scheduler.py 中添加 tick() 定义
```
def tick(verbose=True, adapters=None, loop=None):
    lock_fd = open(LOCK_FILE, 'w')
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    
    due_jobs = get_due_jobs()
    for job in due_jobs:
        advance_next_run(job['id'])
        success, output = run_job(job)
        save_job_output(job['id'], output)
        _deliver_result(job, output, adapters, loop)
        mark_job_run(job['id'], success)
    return len(due_jobs)
```

**修复块2**: 在 gateway/run.py 添加 cron ticker 线程
```
def _start_cron_ticker(stop_event, adapters=None, loop=None):
    while not stop_event.is_set():
        try:
            from cron.scheduler import tick
            tick(verbose=False, adapters=adapters, loop=loop)
        except Exception: pass
        stop_event.wait(timeout=60)
```

### P0-3: CLI 改为 argparse subparsers

**修复块1**: 重构 cli.py 命令分发
```python
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest="command")

chat_p = subparsers.add_parser("chat")
chat_p.set_defaults(func=cmd_chat)

gateway_p = subparsers.add_parser("gateway")
gateway_p.set_defaults(func=cmd_gateway)

cron_p = subparsers.add_parser("cron")
cron_sp = cron_p.add_subparsers(dest="cron_action")
cron_list = cron_sp.add_parser("list")
cron_list.set_defaults(func=cmd_cron_list)

args = parser.parse_args()
args.func(args)  # 一行分发替代百行 if/elif
```

### P0-4: GatewayRunner 生命周期管理

以 Hermes GatewayRunner 为模板，新建 gateway/runner.py：
- `start()` → 连接所有适配器
- `stop()` → drain 活跃 agent → 关闭适配器
- `wait_for_shutdown()` → await shutdown_event
- 信号处理：SIGINT/SIGTERM → stop(), SIGUSR1 → restart()

### P1-1: config.yaml 统一配置

创建 `~/.openclaw/MimirAether/config.yaml`:
```yaml
model:
  default: "deepseek/deepseek-chat"
terminal:
  backend: "local"
  timeout: 300
agent:
  max_turns: 90
cron:
  wrap_response: true
platforms:
  telegram:
    enabled: true
```

加载方式模仿 Hermes config bridging 模式。

### P1-2: BasePlatformAdapter 架构

创建 gateway/platforms/ 目录：
```
gateway/platforms/
  base.py        ← BasePlatformAdapter 抽象基类
  telegram.py    ← TelegramAdapter
  feishu.py      ← FeishuAdapter
  discord.py     ← DiscordAdapter
  local_cli.py   ← 本地 CLI (现有交互模式)
  api.py         ← HTTP API (现有 api_service 逻辑)
```

每个适配器实现 connect/send/message_handler/fatal_error_handler。

---

## 4. 总结

| 维度 | Hermes | MimirAether | 差距 |
|------|--------|-------------|------|
| Gateway 文件大小 | 9003行 | 436行 | 20x |
| 支持平台数 | 20+ | 0 (纯HTTP) | 全缺 |
| Cron tick() | 完整实现(~100行) | 空壳stub | 全缺 |
| CLI 架构 | subparsers | 手动if/elif | 结构化 |
| Config 管理 | config.yaml桥接 | os.environ | 统一化 |
| 会话管理 | SessionStore + agent_cache | 单例AgentManager | 全缺 |

**下一步优先修复 P0 四项**：GatewayRunner + BasePlatformAdapter +
cron tick() 补全 + CLI subparsers 重构。估计工作量约 2000-3000 行。
