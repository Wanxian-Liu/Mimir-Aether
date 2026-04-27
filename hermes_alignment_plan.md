# Hermes → MimirAether 对齐规划

> 制定时间: 2026-04-27
> QA Lead 分析结果

---

## 执行摘要

### 差距分析

| 模块 | Hermes | MimirAether | 差距 |
|------|--------|-------------|------|
| hermes_cli/ | 44文件, main.py 6047行 | 3文件, main.py 653行 | **巨大** |
| agent/ | 29文件, core类 9000+行 | 26文件, core_loop.py 102516字节 | 中等 |
| gateway/ | 16文件, run.py 9003行 | 9文件, run.py 319行 | **巨大** |
| tools/ | 54文件 | 55文件 | 已对齐 |

### 优先级结论

1. **P0 - 紧急**: hermes_cli 核心缺失（main.py 90%未抄）
2. **P0 - 紧急**: gateway/run.py 核心逻辑缺失（96%未抄）
3. **P1 - 高**: hermes_cli 配置系统（config.py 131KB）
4. **P1 - 高**: hermes_cli 认证系统（auth.py 125KB）
5. **P2 - 中**: hermes_cli 工具链（setup/web_server/models等）

---

## 1. 模块优先级排序

### P0 - 核心功能缺失（阻断性）

| 优先级 | 模块 | Hermes规模 | MimirAether规模 | 工作量 |
|--------|------|-----------|----------------|--------|
| P0-1 | hermes_cli/main.py | 6047行 | 653行 | **5小时** |
| P0-2 | gateway/run.py | 9003行 | 319行 | **5小时** |

### P1 - 配置与认证系统

| 优先级 | 模块 | Hermes规模 | MimirAether规模 | 工作量 |
|--------|------|-----------|----------------|--------|
| P1-1 | hermes_cli/config.py | 131KB | 4.3KB | 3小时 |
| P1-2 | hermes_cli/auth.py | 125KB | 0 | 4小时 |
| P1-3 | hermes_cli/providers.py | 21KB | 0 | 1小时 |
| P1-4 | hermes_cli/models.py | 71KB | 0 | 2小时 |

### P2 - 工具与技能系统

| 优先级 | 模块 | Hermes规模 | MimirAether规模 | 工作量 |
|--------|------|-----------|----------------|--------|
| P2-1 | hermes_cli/skills_hub.py | 46KB | 0 | 2小时 |
| P2-2 | hermes_cli/tools_config.py | 70KB | 0 | 2小时 |
| P2-3 | hermes_cli/setup.py | 124KB | 0 | 3小时 |
| P2-4 | hermes_cli/web_server.py | 75KB | 0 | 2小时 |

### P3 - 辅助功能

| 优先级 | 模块 | Hermes规模 | MimirAether规模 | 工作量 |
|--------|------|-----------|----------------|--------|
| P3-1 | hermes_cli/backup.py | 21KB | 0 | 1小时 |
| P3-2 | hermes_cli/cron.py | 10KB | 0 | 0.5小时 |
| P3-3 | hermes_cli/plugins.py | 24KB | 0 | 1小时 |
| P3-4 | 其他 | 30+文件 | 部分 | 5小时 |

---

## 2. hermes_cli 抄写计划

### 2.1 main.py 抄写（P0-1）

**目标**: 将6047行Hermes main.py精简抄写到MimirAether

**核心功能**:
- [ ] 命令行参数解析（chat/gateway/cron/doctor/setup等）
- [ ] Profile管理（--profile/-p）
- [ ] 会话解析（_resolve_session_by_name_or_id）
- [ ] TTY检查（_require_tty）
- [ ] 环境变量注入

**自研改造点**:
- 模块名从`hermes`改为`mimiraether`
- 配置路径从`~/.hermes/`改为`~/.mimiraether/`
- 日志前缀从`[Hermes]`改为`[MimirAether]`

**时间估算**: 5小时

### 2.2 config.py 抄写（P1-1）

**目标**: 抄写131KB配置系统

**核心功能**:
- [ ] YAML配置解析
- [ ] 环境变量展开（_expand_env_vars）
- [ ] 配置验证
- [ ] 默认值填充
- [ ] 多Profile支持

**自研改造点**:
- 适配MimirAether的目录结构
- 增加MimirAether特定配置项

**时间估算**: 3小时

### 2.3 auth.py 抄写（P1-2）

**目标**: 抄写125KB认证系统

**核心功能**:
- [ ] API Key管理
- [ ] OAuth处理
- [ ] Auth文件读写（auth.json）
- [ ] Nous Portal集成
- [ ] OpenRouter集成

**时间估算**: 4小时

### 2.4 其他CLI文件（P1-P3）

```
优先抄写顺序:
1. providers.py (Provider管理) - 1小时
2. models.py (模型配置) - 2小时
3. skills_hub.py (技能中心) - 2小时
4. tools_config.py (工具配置) - 2小时
5. setup.py (安装向导) - 3小时
6. web_server.py (Web服务) - 2小时
7. runtime_provider.py (运行时Provider) - 1小时
8. model_switch.py (模型切换) - 1小时
9. profiles.py (Profile管理) - 1小时
10. banner.py, colors.py, cli_output.py - 0.5小时
11. backup.py, logs.py, status.py - 1小时
12. cron.py, doctor.py, debug.py - 1小时
13. pairing.py, platforms.py - 0.5小时
14. plugins_cmd.py, plugins.py - 1小时
15. webhook.py, clipboard.py - 0.5小时
16. callbacks.py, copilot_auth.py - 1小时
17. curses_ui.py, memory_setup.py - 1小时
18. model_normalize.py, nous_subscription.py - 1小时
19. skills_config.py, skin_engine.py, tips.py - 1小时
20. uninstall.py, default_soul.py, env_loader.py - 0.5小时
```

---

## 3. agent 抄写计划

### 3.1 当前状态

MimirAether的agent/目录已有26个文件，核心模块基本对齐Hermes：

| 模块 | Hermes | MimirAether | 对齐度 |
|------|--------|-------------|--------|
| anthropic_adapter.py | 57KB | 46KB | ✅ 80% |
| auxiliary_client.py | 110KB | 26KB | ⚠️ 24% |
| core_loop.py | N/A | 102KB | 🆕 自研 |
| prompt_builder.py | 46KB | 51KB | ✅ 110% |
| context_compressor.py | 37KB | 26KB | ⚠️ 70% |
| memory_manager.py | 14KB | 21KB | ✅ 150% |
| credential_pool.py | 56KB | 83KB | ✅ 148% |
| context_references.py | 17KB | 34KB | ✅ 200% |
| model_metadata.py | 44KB | 43KB | ✅ 98% |
| insights.py | 34KB | 52KB | ✅ 153% |
| error_classifier.py | 29KB | 30KB | ✅ 103% |

### 3.2 需加强的模块

#### auxiliary_client.py（P1）

**差距**: Hermes 110KB vs MimirAether 26KB

**缺失功能**:
- [ ] Nous Portal集成
- [ ] OpenRouter聚合
- [ ] Provider Chain完整实现
- [ ] 图像格式转换（Anthropic兼容）
- [ ] 支付/连接错误回退

**时间估算**: 3小时

#### context_compressor.py（P2）

**差距**: Hermes 37KB vs MimirAether 26KB

**缺失功能**:
- [ ] DAG构建（分层压缩）
- [ ] 摘要质量评估
- [ ] 压缩历史追踪

**时间估算**: 2小时

### 3.3 自研改造点

| 模块 | Hermes设计 | MimirAether改造 |
|------|-----------|----------------|
| core_loop.py | Hermes AIAgent | 🆕 完全自研，保持 |
| credential_pool.py | 单一凭证 | 增强：多租户支持 |
| insights.py | 基础洞察 | 增强：MimirAether特定洞察 |

---

## 4. gateway 抄写计划

### 4.1 当前状态

| 文件 | Hermes | MimirAether | 对齐度 |
|------|--------|-------------|--------|
| run.py | 9003行 | 319行 | ❌ **4%** |
| session.py | 41632字节 | 11038字节 | ⚠️ 27% |
| config.py | 50799字节 | 7711字节 | ⚠️ 15% |
| stream_consumer.py | 33093字节 | 0 | ❌ 0% |
| channel_directory.py | 9644字节 | 0 | ❌ 0% |
| display_config.py | 6427字节 | 0 | ❌ 0% |
| hooks.py | 6427字节 | 0 | ❌ 0% |
| status.py | 14240字节 | 0 | ❌ 0% |
| pairing.py | 11468字节 | 0 | ❌ 0% |

### 4.2 run.py 核心抄写（P0-2）

**目标**: 将9003行Hermes gateway/run.py精简抄写

**核心架构**:
```python
# Hermes gateway架构
GatewayRunner
├── _load_config()        # 加载配置
├── _load_adapters()     # 加载平台适配器
├── _start_all()          # 启动所有适配器
├── _setup_signal_handling()  # 信号处理
└── _graceful_shutdown() # 优雅关闭

Platform Adapters
├── DiscordAdapter
├── TelegramAdapter
├── FeishuAdapter
├── SlackAdapter
└── ...
```

**缺失功能**:
- [ ] SSL证书自动检测（_ensure_ssl_certs）
- [ ] 配置展开（config.yaml → env）
- [ ] 平台适配器动态加载
- [ ] 会话管理完整实现
- [ ] WebSocket支持
- [ ] 消息队列集成
- [ ] 内置Hook系统

**自研改造点**:
- 适配MimirAether的目录结构
- 使用MimirAether的日志系统
- 适配OpenClaw的channel系统

**时间估算**: 5小时

### 4.3 session.py 增强（P1）

**目标**: 扩展现有session.py到Hermes水平

**缺失功能**:
- [ ] 会话持久化
- [ ] 会话恢复
- [ ] 并发会话管理
- [ ] 会话清理

**时间估算**: 2小时

### 4.4 其他Gateway文件（P2-P3）

```
1. stream_consumer.py (流消费) - 1小时
2. channel_directory.py (渠道目录) - 0.5小时
3. display_config.py (显示配置) - 0.5小时
4. hooks.py (Hook系统) - 1小时
5. status.py (状态管理) - 1小时
6. pairing.py (配对) - 0.5小时
7. builtin_hooks/ (内置Hook) - 1小时
8. platforms/ (平台特定) - 2小时
9. restart.py, sticker_cache.py, mirror.py - 0.5小时
```

---

## 5. 自研改造点清单

### 5.1 架构改造

| # | 改造点 | Hermes实现 | MimirAether改造 | 优先级 |
|---|--------|-----------|----------------|--------|
| 1 | 核心循环 | AIAgent | 🆕 core_loop.py自研 | 保持 |
| 2 | 凭证池 | 单一凭证池 | 多租户支持 | P1 |
| 3 | 工具注册 | tools/registry | mimircore_tool | P1 |
| 4 | 上下文压缩 | 分层DAG | 可插拔引擎 | P2 |

### 5.2 功能改造

| # | 改造点 | Hermes实现 | MimirAether改造 | 优先级 |
|---|--------|-----------|----------------|--------|
| 1 | MCP支持 | mcp_tool | 保留+增强 | P1 |
| 2 | 技能系统 | skills_hub | 自研SkillManager | P1 |
| 3 | 记忆系统 | 外部Honcho | 内置MemoryFencer | P1 |
| 4 | 终端工具 | terminal_tool | 保留 | P2 |

### 5.3 集成改造

| # | 改造点 | Hermes实现 | MimirAether改造 | 优先级 |
|---|--------|-----------|----------------|--------|
| 1 | OpenClaw | 无 | 🆕 channel系统 | P0 |
| 2 | OpenClaw | 无 | 🆕 Gateway集成 | P0 |
| 3 | OpenClaw | 无 | 🆕 Subagent支持 | P1 |
| 4 | OpenClaw | 无 | 🆕 Hook系统 | P2 |

---

## 6. 5小时执行计划

### Phase 1: P0核心对齐（2小时）

#### Hour 1-2: hermes_cli/main.py 核心抄写

**目标**: 实现CLI主入口，支撑基本交互

```
[ ] 任务1: 抄写命令解析框架（1小时）
    - chat命令
    - gateway命令（start/stop/restart/status）
    - 基础参数（--profile/-p, --model等）

[ ] 任务2: 抄写Profile管理（0.5小时）
    - _apply_profile_override()
    - HERMES_HOME → MIMIRAETHER_HOME

[ ] 任务3: 抄写会话解析（0.5小时）
    - _resolve_session_by_name_or_id()
    - SessionDB集成
```

### Phase 2: Gateway核心（2小时）

#### Hour 3-4: gateway/run.py 核心抄写

**目标**: 实现Gateway主循环

```
[ ] 任务4: 抄写SSL和配置初始化（0.5小时）
    - _ensure_ssl_certs()
    - config.yaml解析

[ ] 任务5: 抄写GatewayRunner骨架（1小时）
    - load_adapter()
    - start/stop/restart
    - 信号处理

[ ] 任务6: 抄写平台适配器加载（0.5小时）
    - 适配MimirAether/adapter.py
    - 适配MimirAether/feishu_adapter.py
```

### Phase 3: 验证与文档（1小时）

```
[ ] 任务7: 端到端验证（0.5小时）
    - hermes_cli/main.py --help
    - gateway/run.py --help
    - 基本交互测试

[ ] 任务8: 文档更新（0.5小时）
    - 更新hermes_alignment_plan.md状态
    - 记录未完成项
```

---

## 附录

### A. 文件对应关系

#### hermes_cli/ 文件映射

| Hermes文件 | MimirAether文件 | 状态 |
|------------|-----------------|------|
| main.py | main.py | ⚠️ 部分抄写 |
| config.py | config.py | ⚠️ 部分抄写 |
| auth.py | ❌ | 待抄写 |
| gateway.py | ❌ | 待整合 |
| models.py | ❌ | 待抄写 |
| providers.py | ❌ | 待抄写 |
| setup.py | ❌ | 待抄写 |
| web_server.py | ❌ | 待抄写 |
| tools_config.py | ❌ | 待抄写 |
| skills_hub.py | ❌ | 待抄写 |
| ... | ... | ... |

#### agent/ 文件映射

| Hermes文件 | MimirAether文件 | 对齐度 |
|------------|-----------------|--------|
| anthropic_adapter.py | anthropic_adapter.py | ✅ 80% |
| auxiliary_client.py | auxiliary_client.py | ⚠️ 24% |
| context_engine.py | context_engine.py | ✅ 85% |
| context_compressor.py | context_compressor.py | ⚠️ 70% |
| memory_manager.py | memory_manager.py | ✅ 150% |
| prompt_builder.py | prompt_builder.py | ✅ 110% |
| credential_pool.py | credential_pool.py | ✅ 148% |
| model_metadata.py | model_metadata.py | ✅ 98% |
| insights.py | insights.py | ✅ 153% |
| error_classifier.py | error_classifier.py | ✅ 103% |
| ... | core_loop.py | 🆕 自研 |

#### gateway/ 文件映射

| Hermes文件 | MimirAether文件 | 对齐度 |
|------------|-----------------|--------|
| run.py | run.py | ❌ 4% |
| session.py | session.py | ⚠️ 27% |
| config.py | adapter.py | ⚠️ 部分 |
| stream_consumer.py | ❌ | 待抄写 |
| channel_directory.py | ❌ | 待抄写 |
| display_config.py | ❌ | 待抄写 |
| hooks.py | ❌ | 待抄写 |
| status.py | ❌ | 待抄写 |
| pairing.py | ❌ | 待抄写 |
| builtin_hooks/ | ❌ | 待抄写 |
| platforms/ | discord/telegram/feishu adapters | ⚠️ 部分 |

### B. 工作量估算汇总

| Phase | 任务 | 估算时间 |
|-------|------|----------|
| Phase 1 | hermes_cli/main.py | 2小时 |
| Phase 2 | gateway/run.py | 2小时 |
| Phase 3 | 验证与文档 | 1小时 |
| **总计** | | **5小时** |

### C. 后续任务（5小时之外）

```
P1优先级（额外5小时）:
- hermes_cli/auth.py (4小时)
- hermes_cli/config.py (1小时)

P2优先级（额外10小时）:
- hermes_cli剩余文件
- agent/auxiliary_client.py增强
- gateway/session.py增强
- tools/对齐

P3优先级（额外10小时）:
- 其他hermes_cli文件
- 其他gateway文件
- 完整测试
```

---

**文档状态**: ✅ 分析完成
**下次更新**: Phase 1完成后
