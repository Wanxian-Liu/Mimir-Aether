# MimirAether自研改造计划

> 分析日期: 2026-04-27
> 总计: hermes_cli 36处TODO-自研, gateway 162处TODO-自研

---

## 改造方向总结

| 方向 | 说明 | 涉及文件数 |
|------|------|-----------|
| 品牌替换 | hermes → MimirAether/mimir | ~25 |
| 路径适配 | ~/.hermes/ → ~/.openclaw/ | ~8 |
| 依赖替换 | Hermes特定依赖 → OpenClaw实现 | ~15 |

---

## P0 - 必须立即改造（阻断功能）

这些是阻塞性问题，不改造则系统无法运行。

### 1. 核心路径引用 (~15处)
| 文件 | 行号 | 改造内容 | 影响 |
|------|------|----------|------|
| gateway/config.py | 221,224,250,393,445,449,450,453 | `get_hermes_home()` → `get_openclaw_home()`，路径 `~/.hermes/` → `~/.openclaw/` | 配置文件读取失败 |
| gateway/config.py | 732 | 移除 `hermes_cli.auth` 依赖 | 认证流程中断 |
| gateway/run.py | 84 | 替换 `hermes_constants.get_hermes_home` | Gateway无法启动 |
| gateway/run.py | 94 | 替换 `hermes_cli.env_loader.load_hermes_dotenv` | 环境变量加载失败 |
| gateway/run.py | 115 | 替换 `hermes_logging.setup_logging` | 日志系统不可用 |
| hermes_cli/config.py | 553 | `get_hermes_home` → `get_mimir_home` | CLI路径错误 |

### 2. 核心导入依赖 (~10处)
| 文件 | 改造内容 | 影响 |
|------|----------|------|
| gateway/hermes_status.py | `from hermes_cli.config import get_hermes_home` | 状态检查失败 |
| gateway/restart.py | `from hermes_cli.config import _get_default_config` | 重启功能失败 |
| gateway/hooks.py | `hermes_cli.config` → OpenClaw配置 | Hook系统不可用 |
| gateway/run.py:310 | 替换 hermes-specific 初始化 | Gateway启动失败 |
| gateway/run.py:327 | 替换 `tools.process_registry` | 进程管理失效 |
| gateway/run.py:387 | 替换 `hermes_state.SessionDB` | 会话持久化失效 |
| gateway/run.py:395 | 替换 `gateway.pairing.PairingStore` | 配对存储失效 |

### 3. 品牌标识 (~20处)
| 文件 | 改造内容 |
|------|----------|
| hermes_cli/__init__.py | 版本号与MimirAether同步 |
| 所有hermes_cli文件头部 | `# TODO-自研: 本文件从hermes-agent抄写` → 移除或更新 |
| gateway/run.py | `# TODO-自研: Gateway运行入口` → MimirAether |

**P0预计改造时间: 6-8小时**

---

## P1 - 重要改造（提升功能）

这些改造提升功能完整性，不阻断但影响核心体验。

### 1. Session与Memory适配 (~15处)
| 文件 | 行号 | 改造内容 |
|------|------|----------|
| gateway/run.py | 458,469,471 | `_flush_memories_for_session` - OpenClaw memory API适配 |
| gateway/run.py | 520 | `_resolve_session_agent_runtime` - agent runtime适配 |
| gateway/run.py | 612,616,620 | 预填充消息/临时系统提示词/reasoning配置 |

### 2. Skill系统适配 (~8处)
| 文件 | 行号 | 改造内容 |
|------|------|----------|
| gateway/run.py | 225,228,419 | `_check_unavailable_skill` - OpenClaw skill检查 |
| hermes_cli/runtime_provider.py | 31 | `get_compatible_custom_providers` 适配 |

### 3. Model路由适配 (~5处)
| 文件 | 行号 | 改造内容 |
|------|------|----------|
| gateway/run.py | 245 | OpenClaw model resolution |
| gateway/run.py | 553,646,650,654 | 动态模型路由/fallback/智能路由 |
| hermes_cli/model_switch.py | 40,782 | `get_model_info/get_model_capabilities` |

### 4. Hook系统完善 (~10处)
| 文件 | 行号 | 改造内容 |
|------|------|----------|
| gateway/hooks.py | 17,18,22,23,48,74,106 | Hook目录/前缀/内置Hook适配 |
| gateway/hooks.py | 48,74 | `builtin_hooks` 路径适配 |

**P1预计改造时间: 10-12小时**

---

## P2 - 优化改造（长期）

这些是锦上添花的优化，可分阶段进行。

### 1. 媒体处理 (~3处)
| 文件 | 行号 | 改造内容 |
|------|------|----------|
| gateway/run.py | 211 | `_build_media_placeholder` - OpenClaw媒体处理 |
| gateway/delivery.py | 67 | 媒体文件分发扩展 |

### 2. 投递策略优化 (~5处)
| 文件 | 行号 | 改造内容 |
|------|------|----------|
| gateway/delivery.py | 25,40 | 投递队列/重试机制/优先级调度 |
| gateway/run.py | 340 | DeliveryRouter适配 |
| gateway/delivery.py | 4,40 | 消息投递与媒体分发 |

### 3. 跨渠道同步 (~5处)
| 文件 | 行号 | 改造内容 |
|------|------|----------|
| gateway/mirror.py | 16,35,48,87 | 消息转换/格式化/过滤/队列 |
| gateway/channel_directory.py | 16,25 | 动态注册/优先级权重 |

### 4. Agent生命周期 (~5处)
| 文件 | 行号 | 改造内容 |
|------|------|----------|
| gateway/run.py | 689,694,704,718 | 排水逻辑/中断/关闭/detached restart |
| gateway/run.py | 448,453 | TTS禁用/voice mode sync |

**P2预计改造时间: 15-20小时**

---

## 关键依赖关系图

```
P0 (先改)
├── config.py 路径适配
├── run.py 核心启动链
└── hermes_cli 品牌替换
    ↓
P1 (后改)
├── Session/Memory适配
├── Skill系统适配
└── Model路由适配
    ↓
P2 (最后)
├── 媒体处理
├── 投递优化
└── 高级特性
```

---

## 快速执行清单

### Step 1: 路径统一 (30分钟)
```bash
# 在所有文件中执行路径替换
~/.hermes/ → ~/.openclaw/
get_hermes_home → get_openclaw_home/get_mimir_home
```

### Step 2: 品牌替换 (1小时)
```bash
# 搜索替换品牌标识
Hermes → MimirAether
hermes_cli → mimir_cli
HermesStatus → MimirStatus
```

### Step 3: 依赖解耦 (2-3小时)
```python
# 替换Hermes特定依赖
from hermes_cli.auth import ...
from hermes_state import SessionDB
from hermes_constants import ...

# 替换为OpenClaw对应实现
from openclaw.config import ...
from openclaw.state import SessionDB
from openclaw.constants import ...
```

### Step 4: 功能验证 (1-2小时)
```bash
# 验证Gateway启动
python -m gateway.run

# 验证CLI可用
python -m hermes_cli --version
```

---

## 预计总改造时间

| 阶段 | 时间 | 说明 |
|------|------|------|
| P0 | 6-8小时 | 核心路径+依赖+品牌 |
| P1 | 10-12小时 | Session/Skill/Model适配 |
| P2 | 15-20小时 | 媒体/投递/高级特性 |
| **总计** | **31-40小时** | 分3-4周完成 |

---

## 建议执行顺序

1. **第一周**: 完成P0所有改造 + 基础验证
2. **第二周**: 完成P1 Session/Memory/Skill适配
3. **第三周**: 完成P1 Model路由 + 开始P2
4. **第四周**: 完成P2 + 全面测试

---

*本计划由QA Lead制定，等待确认后执行*
