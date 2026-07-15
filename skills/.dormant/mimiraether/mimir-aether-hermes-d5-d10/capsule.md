# [DORMANT] mimir-aether-hermes-d5-d10

**沉寂时间**: 2026-07-14T19:39:05.285703+00:00
**原始分类**: mimiraether
**描述**: Hermes Agent核心源码系统学习 - 涵盖Day 5-12的platforms、gateway、cli、cron、agent、tools等模块的架构分析与集成参考
**触发阈值**: 60天未触碰

---

## 技能要点

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
hermes chat              

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimir-aether-hermes-d5-d10")` 即可自动唤醒。
