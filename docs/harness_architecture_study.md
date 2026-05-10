# Harness → MimirAether 架构迁移研究报告

> 生成时间: 2026-05-10 | 分析对象: harness/harness (Go) vs MimirAether (Python)

---

## 一、Harness Go 架构概览

### 1.1 项目元数据

| 属性 | 值 |
|------|-----|
| 语言 | Go + TypeScript (前端) |
| Stars | 35k+ |
| 架构风格 | 单体应用 (Monolith)，非微服务 |
| 二进制名 | `gitness` |
| 入口 | `cmd/gitness/main.go` |
| DI框架 | Google Wire (`wire.go` + `wire_gen.go`) |
| 通信协议 | REST (Swagger/OpenAPI) + gRPC (protobuf) |
| 前端 | TypeScript (`web/` 目录) |
| 部署 | Docker 单体镜像 |

### 1.2 顶层目录结构

```
harness/
├── cmd/gitness/          # 唯一入口点 (main.go + wire DI)
├── app/                  # 主应用包 (核心业务逻辑)
│   ├── api/              # HTTP API 层
│   │   ├── controller/   # 业务控制器 (按领域实体分)
│   │   ├── handler/      # HTTP 请求处理器 (按领域实体分)
│   │   ├── auth/         # 资源级授权中间件
│   │   ├── middleware/   # 请求中间件链
│   │   ├── openapi/      # Swagger 规范
│   │   └── render/       # 响应渲染器
│   ├── services/         # 业务服务层 (30+ 服务)
│   ├── store/            # 数据持久化层 (SQLite/PostgreSQL)
│   ├── pipeline/         # CI/CD Pipeline 引擎
│   ├── gitspace/         # 开发环境管理
│   ├── events/           # 领域事件系统
│   ├── connector/        # 外部连接器 (SCM等)
│   ├── auth/             # 认证/授权
│   ├── config/           # 配置管理
│   ├── router/           # HTTP 路由
│   ├── server/           # HTTP Server
│   ├── bootstrap/        # 启动引导
│   ├── cron/             # 定时任务
│   └── sse/              # Server-Sent Events
├── cli/                  # CLI 客户端操作
│   └── operations/       # CLI 命令 (server/user/account/...)
├── git/                  # Git 操作库
├── events/               # 通用事件系统
├── store/                # 通用存储层
├── types/                # 共享类型定义
├── pubsub/               # 发布订阅
├── job/                  # 后台任务
├── lock/                 # 分布式锁
├── stream/               # 流处理
├── errors/               # 错误处理
├── web/                  # TypeScript 前端
└── Dockerfile            # 容器化
```

### 1.3 核心架构模式

#### 三层架构 (Controller → Service → Store)

```
HTTP Request → Handler → Controller → Service → Store → DB
                   ↑           ↑          ↑        ↑
               Middleware    Auth     Events    Cache
```

**示例 (connector)**:
```
app/api/controller/connector/
    controller.go    # 控制器入口
    create.go        # 创建逻辑
    update.go        # 更新逻辑
    delete.go        # 删除逻辑
    find.go          # 查询逻辑
    test.go          # 测试连接
    wire.go          # DI 绑定

app/api/handler/connector/     # HTTP Handler (REST)
app/api/auth/connector.go      # 资源级鉴权
app/services/connector/        # 业务服务 (如有)
app/store/database/connector/  # 数据库操作
```

#### 按领域实体垂直切分

每个领域实体 (check, connector, execution, pipeline, pullreq, repo, secret, space, user, webhook...) 都有独立的三层实现，且文件以操作命名 (CRUD)。

#### Middleware 洋葱模型

```
Request → nocache → authn → authz → principal → logging → encode → Handler
```

#### Wire DI 依赖注入

```go
// cmd/gitness/wire.go - 声明依赖关系
// cmd/gitness/wire_gen.go - 自动生成注入代码
```

### 1.4 关键架构决策

| 决策 | 实现 |
|------|------|
| **单一二进制** | `cmd/gitness` 同时是 server + CLI |
| **领域事件驱动** | `app/events/` 下每个领域有独立事件 |
| **Swagger 驱动 API** | `./gitness swagger` 生成 OpenAPI spec → 前端 TS 客户端 |
| **Pipeline 沙箱** | Docker 容器中执行 CI/CD pipeline |
| **双数据库支持** | SQLite (开发) + PostgreSQL (生产) |
| **配置驱动** | `.local.env` 环境变量文件 |

---

## 二、MimirAether 项目结构

### 2.1 项目概览

| 属性 | 值 |
|------|-----|
| 语言 | Python 3 |
| 核心文件数 | ~90 .py 文件 (仅顶层+agent/) |
| 代码规模 | ~17000 行核心 Python |
| 最大单文件 | `gateway/run.py` (426KB), `cli.py` (212KB), `agent/core_loop.py` (113KB) |

### 2.2 关键模块

```
MimirAether/
├── cli.py                    # 🟡 CLI 入口 (212KB 单体巨石)
├── api_service.py            # HTTP API 服务 (OpenAI 兼容)
├── mcp_serve.py              # MCP 协议服务
├── batch_runner.py           # 批量任务执行
├── agent/                    # 核心 Agent 模块
│   ├── __init__.py           # 模块导出聚合
│   ├── core_loop.py          # 🟡 主循环 (113KB)
│   ├── turn_loop.py          # 回合管理
│   ├── subagent.py           # 子代理管理
│   ├── context_compressor.py # 上下文压缩
│   ├── credential_pool.py    # 凭证池 (83KB!)
│   ├── anthropic_adapter.py  # Anthropic 适配器
│   ├── prompt_builder.py     # Prompt 构建
│   ├── smart_model_routing.py# 模型路由
│   ├── error_classifier.py   # 错误分类
│   ├── rate_limit_tracker.py # 速率限制
│   ├── memory_manager.py     # 记忆管理
│   ├── session_tracker.py    # 会话追踪
│   ├── skills_hub.py         # 技能中心
│   ├── display.py            # 显示/渲染 (40KB)
│   ├── insights.py           # 分析洞察 (52KB)
│   ├── usage_pricing.py      # 用量计费
│   └── ... (30+ 子模块)
├── gateway/                  # 网关模块
│   ├── run.py                # 🟡 网关主循环 (426KB!)
│   ├── session.py            # 会话管理 (44KB)
│   ├── config.py             # 配置 (51KB)
│   ├── adapter.py            # 平台适配器
│   ├── router.py             # 消息路由
│   ├── channel_directory.py  # 渠道目录
│   └── ...
├── tools/                    # 工具模块
│   ├── browser_tool.py       # 浏览器工具 (96KB)
│   ├── web_tools.py          # Web 工具 (87KB)
│   ├── mcp_tool.py           # MCP 工具 (87KB)
│   ├── code_execution_tool.py# 代码执行
│   ├── terminal_tool.py      # 终端工具 (74KB)
│   ├── file_operations.py    # 文件操作
│   └── ... (30+ 工具)
├── mimicore/                 # 子项目
│   ├── agent/ classifier/ config/ evolve/
│   ├── extractor/ fence/ health/ permission/
│   ├── pipeline/ plugin/ sensory/ task/ wal/
│   └── ...
├── scheduler/                # 定时任务调度
├── skills/ + optional-skills/# 技能系统 (100+ 技能)
├── docs/                     # 文档
└── tests/                    # 测试分散在各处
```

### 2.3 当前架构问题诊断

| 问题 | 严重度 | 说明 |
|------|--------|------|
| **文件过大** | 🔴🔴🔴 | `gateway/run.py` 426KB, `cli.py` 212KB, `core_loop.py` 113KB |
| **层级模糊** | 🔴🔴 | agent/ 混合了业务逻辑/基础设施/适配器/工具，没有清晰的 Controller/Service/Store 分层 |
| **模块粒度不一致** | 🔴 | `credential_pool.py` 83KB vs `utils.py` 仅 164 行 |
| **测试分散** | 🟡 | 测试文件散布在 agent/ 下，没有独立 tests/ 目录 |
| **重复代码** | 🟡 | `.bak` 文件保留 (`approval.py.bak`, `delegate_tool.py.bak`) |
| **依赖注入缺失** | 🟡 | 硬编码的导入依赖，无可替换性 |
| **Gateway 耦合严重** | 🔴🔴 | `run.py` 包含会话/路由/配置/消息处理于一体 |

---

## 三、可复用设计模式 (5个)

### 模式 1: Controller-Handler-Service 三层分离

**Harness 实践:**
```
app/api/controller/<entity>/  # 纯业务逻辑，不依赖 HTTP
app/api/handler/<entity>/     # HTTP 层，解析请求/序列化响应
app/services/<entity>/        # 跨控制器复用的业务服务
```

**对 MimirAether 的启示:**
当前 `agent/core_loop.py` 混合了消息处理、LLM调用、工具执行、上下文管理、记忆操作——所有职责在一个 113KB 文件中。

**建议拆分:**
```python
agent/
├── controllers/          # 业务逻辑层
│   ├── message_controller.py   # 消息处理
│   ├── turn_controller.py      # 回合管理
│   └── tool_controller.py      # 工具调用编排
├── handlers/             # 协议适配层
│   ├── http_handler.py          # HTTP/SSE 请求处理
│   └── websocket_handler.py     # WebSocket
├── services/             # 可复用业务服务
│   ├── llm_service.py           # LLM 调用服务
│   ├── memory_service.py        # 记忆服务
│   ├── credential_service.py    # 凭证管理
│   └── routing_service.py       # 模型路由
└── repositories/         # 数据访问层
    ├── session_repo.py
    └── checkpoint_repo.py
```

### 模式 2: 领域事件驱动架构

**Harness 实践:**
```go
app/events/
├── check/       # Check 事件
├── git/         # Git 事件
├── pipeline/    # Pipeline 事件
├── pullreq/     # PR 事件
├── repo/        # Repo 事件
└── user/        # User 事件
```

每个领域事件独立定义，通过 pubsub 系统解耦。

**对 MimirAether 的启示:**
当前 agent 中各模块通过直接函数调用耦合。引入事件总线可以：

```python
# 事件定义
class AgentEvent:
    TURN_STARTED = "agent.turn.started"
    TURN_COMPLETED = "agent.turn.completed"
    TOOL_CALLED = "agent.tool.called"
    ERROR_OCCURRED = "agent.error.occurred"
    SESSION_CREATED = "agent.session.created"
    MEMORY_UPDATED = "agent.memory.updated"

# 订阅者解耦
event_bus.subscribe("agent.turn.completed", session_tracker.on_turn_completed)
event_bus.subscribe("agent.turn.completed", insights_engine.on_turn_completed)
event_bus.subscribe("agent.tool.called", usage_pricing.on_tool_called)
```

**优势:**
- 模块间零耦合
- 新增监控/审计只需订阅事件
- 可独立测试每个订阅者

### 模式 3: Wire 式依赖注入 → Python 适配

**Harness 实践:**
Google Wire 在编译时生成依赖注入代码，确保所有依赖在启动时解析完成。

**对 MimirAether 的建议 (Python 版本):**

```python
# app_container.py - 应用容器
class AppContainer:
    """Wire 风格的依赖注入容器"""
    
    def __init__(self, config: Config):
        self._config = config
        self._instances = {}
    
    def credential_pool(self) -> CredentialPool:
        if 'credential_pool' not in self._instances:
            self._instances['credential_pool'] = CredentialPool(
                config=self._config,
                store=self.credential_store()
            )
        return self._instances['credential_pool']
    
    def llm_service(self) -> LLMService:
        if 'llm_service' not in self._instances:
            self._instances['llm_service'] = LLMService(
                credential_pool=self.credential_pool(),
                routing_service=self.routing_service()
            )
        return self._instances['llm_service']
```

**替代方案:** 使用 `dependency-injector` 库或 Python 的 `contextvars`。

### 模式 4: CLI + Server 统一二进制

**Harness 实践:**
```bash
./gitness server .local.env    # 启动服务器
./gitness login                # CLI 登录
./gitness user pat "uid" 2592000  # CLI 管理
./gitness swagger              # 生成 API 文档
```

单一二进制同时支持 server 模式和 CLI 管理模式。

**对 MimirAether 的启示:**
当前 `cli.py` 是 212KB 的巨石文件，应拆分为:

```python
# 统一入口
# cli.py → 路由到子命令
python -m mimiraether serve          # 启动服务
python -m mimiraether run "任务"     # 单次任务
python -m mimiraether status         # 状态检查
python -m mimiraether doctor         # 诊断
python -m mimiraether config         # 配置管理
python -m mimiraether cron list      # 定时任务
python -m mimiraether api generate   # 生成 OpenAPI spec
```

拆分策略:
```python
cli/
├── __init__.py
├── main.py              # 入口，argparse 路由
├── commands/
│   ├── serve.py         # 服务启动
│   ├── run.py           # 任务执行
│   ├── status.py        # 状态
│   ├── doctor.py        # 诊断
│   ├── config.py        # 配置
│   └── cron.py          # 定时任务
└── display/
    └── formatters.py    # 输出格式化
```

### 模式 5: 配置驱动的模块启动

**Harness 实践:**
```go
// app/bootstrap/ - 按依赖顺序初始化所有组件
func Bootstrap(config *Config) (*Server, error) {
    db := initDatabase(config)
    store := initStore(db)
    services := initServices(store)
    controllers := initControllers(services)
    handlers := initHandlers(controllers)
    middleware := initMiddleware(config)
    router := initRouter(handlers, middleware)
    return initServer(router, config)
}
```

**对 MimirAether 的启示:**
当前启动逻辑分散在 `cli.py`、`gateway/run.py`、`api_service.py` 中，各启动各的。

集中式启动引导:
```python
# bootstrap.py
class ApplicationBootstrap:
    """按依赖顺序初始化所有组件"""
    
    def __init__(self, config_path: str):
        self.config = Config.load(config_path)
    
    async def bootstrap(self) -> Application:
        # 层1: 基础设施
        db = await self._init_database()
        event_bus = self._init_event_bus()
        
        # 层2: 数据访问
        repos = self._init_repositories(db)
        
        # 层3: 领域服务
        services = self._init_services(repos, event_bus)
        
        # 层4: 控制器
        controllers = self._init_controllers(services)
        
        # 层5: 传输层
        handlers = self._init_handlers(controllers)
        
        # 层6: 中间件
        middleware = self._init_middleware()
        
        # 层7: 应用
        return Application(
            handlers=handlers,
            middleware=middleware,
            event_bus=event_bus,
            config=self.config
        )
```

---

## 四、MimirAether 架构改进建议

### 4.1 立即行动 (本周)

| 优先级 | 行动 | 影响 |
|--------|------|------|
| P0 | 拆分 `gateway/run.py` (426KB) → 按职责分文件 | 可维护性 +300% |
| P0 | 拆分 `cli.py` (212KB) → `cli/commands/*.py` | CLI 可测试性 |
| P0 | 删除 `.bak` 文件, 清理 `capsule_input_*.txt` (26个) | 项目清洁度 |

### 4.2 短期改进 (本月)

| 优先级 | 行动 | 参考模式 |
|--------|------|----------|
| P1 | 引入三层架构: `agent/controllers/`, `agent/services/`, `agent/repositories/` | 模式1 |
| P1 | 拆分 `agent/core_loop.py` (113KB) 到各层 | 模式1 |
| P1 | 引入事件总线 (解耦 session_tracker, insights, usage_pricing) | 模式2 |
| P1 | 建立 `bootstrap.py` 统一启动流程 | 模式5 |

### 4.3 中期改进 (下季度)

| 优先级 | 行动 | 参考模式 |
|--------|------|----------|
| P2 | 引入 DI 容器 (`AppContainer`) 替代硬编码导入 | 模式3 |
| P2 | `mimicore/` 与主项目明确边界 (独立 package 或合并) | 模式1 |
| P2 | 统一 `agent/__init__.py` 为清晰的公开 API | 模式3 |
| P2 | 建立 OpenAPI spec 自动生成 (`mimiraether api generate`) | 模式4 |

### 4.4 长期愿景

| 优先级 | 行动 | 说明 |
|--------|------|------|
| P3 | Gateway 解耦: session/route/config → 独立服务 | HTTP API / WebSocket / CLI 三通道清晰分离 |
| P3 | 测试架构: 按层编写 (controller test → service test → repo test) | 参考 Harness 的 `_test.go` 与源文件同目录策略 |
| P3 | 插件化工具系统: 每个工具独立 package，动态加载 | 参考 Harness 的 connector 模式 |

---

## 五、优先级排序

```
P0 (本周 - 解耦巨石文件)
├── gateway/run.py: 426KB → 拆分为 session.py + router.py + server.py + ...
├── cli.py: 212KB → 拆分为 cli/commands/{serve,run,status,doctor,config,cron}.py
└── 清理工作: 删除 .bak 文件, 整理测试文件

P1 (本月 - 建立清晰分层)
├── agent/ 三层架构: controllers/ → services/ → repositories/
├── agent/core_loop.py 拆分到各层
├── 事件总线: pubsub 解耦
└── bootstrap.py: 统一启动流程

P2 (下季度 - 基础设施)
├── DI 容器
├── mimicore/ 边界明确化
└── OpenAPI 自动生成

P3 (长期 - 架构进化)
├── Gateway 服务化
├── 测试架构标准化
└── 工具插件化
```

---

### 附录: 文件大小排名 (当前 MimirAether 巨石文件)

| 文件 | 大小 | 风险 |
|------|------|------|
| `gateway/run.py` | 426KB | 🔴 严重 - 不可测试 |
| `cli.py` | 212KB | 🔴 严重 - 不可维护 |
| `agent/core_loop.py` | 113KB | 🔴 严重 - 职责不清 |
| `agent/auxiliary_client.py` | 111KB | 🔴 严重 |
| `tools/browser_tool.py` | 96KB | 🟡 |
| `tools/web_tools.py` | 87KB | 🟡 |
| `tools/mcp_tool.py` | 87KB | 🟡 |
| `agent/credential_pool.py` | 83KB | 🟡 |
| `tools/terminal_tool.py` | 74KB | 🟡 |
| `tools/send_message_tool.py` | 45KB | 🟢 |

---
*报告结束 | 琬弦 🧵 基于 Harness 架构研究生成*
