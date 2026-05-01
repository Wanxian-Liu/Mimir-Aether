# Week 3 差距分析报告：Gateway、Cron、CLI

## 1. Cron模块对比

### Hermes实现 (完整)
```
hermes-agent/cron/
├── __init__.py      (doc + exports)
├── jobs.py          (26KB - Job CRUD + Schedule解析)
└── scheduler.py     (39KB - tick执行 + 投递)
```

**核心功能：**
- Job CRUD: create_job, get_job, list_jobs, update_job, remove_job
- pause_job, resume_job, trigger_job
- Schedule解析: interval, cron表达式, one-shot, duration
- 文件锁防止重复执行
- 自动投递到origin/platform
- 预运行脚本支持

### MimirAether现状
```
MimirAether/cron/
├── jobs.json        (仅有示例)
├── delivery/        (空目录)
└── output/         (空目录)
```

**差距分析：**
| 功能 | Hermes | MimirAether | 状态 |
|------|--------|-------------|------|
| Job存储 | JSON + 原子写入 | ❌ 无 | P1 |
| Schedule解析 | 完整 | ❌ 无 | P1 |
| Cron表达式 | croniter | ❌ 无 | P1 |
| Job执行 | tick循环 | ❌ 无 | P1 |
| 投递系统 | 完整 | ⚠️ 框架 | P2 |

---

## 2. Gateway模块对比

### Hermes实现
- `gateway/run.py`: 9003行
- 完整的平台适配器管理
- SSL自动检测
- 环境变量加载
- Session管理
- Stream消费
- Hook系统

### MimirAether现状
```
gateway/
├── run.py          (415KB - 从Hermes复制)
├── config.py       (已适配)
├── channel_directory.py (已适配)
├── delivery.py     (已适配)
├── hooks.py        (已适配)
├── adapter.py      (MimirAether新增)
├── router.py       (MimirAether新增)
└── message.py      (MimirAether新增)
```

**差距分析：**
| 功能 | Hermes | MimirAether | 状态 |
|------|--------|-------------|------|
| 平台适配 | 18+平台 | ⚠️ 基础3平台 | P2 |
| Webhook处理 | 完整 | ⚠️ 待验证 | P2 |
| 消息投递 | 完整 | ⚠️ 待验证 | P2 |
| Session管理 | 完整 | ✅ 已有 | P3 |

---

## 3. CLI模块对比

### Hermes实现
- `cli.py`: 446KB
- 完整的命令系统
- 交互式模式
- 服务安装
- 健康检查
- 配置管理

### MimirAether CLI (21KB)
```python
# 现有命令
- status      (基本)
- config      (基本)
- doctor      (基本)
- setup       (向导)
- model       (选择)
- cron list   (占位)
- version
- -q 模式     (单次)
```

**差距分析：**
| 功能 | Hermes | MimirAether | 状态 |
|------|--------|-------------|------|
| cron create | 完整 | ❌ 无 | P1 |
| cron delete | 完整 | ❌ 无 | P1 |
| cron pause/resume | 完整 | ❌ 无 | P1 |
| cron trigger | 完整 | ❌ 无 | P1 |
| gateway install | 完整 | ❌ 无 | P2 |
| skill install | 完整 | ⚠️ 基础 | P2 |
| agent spawn | 完整 | ❌ 无 | P3 |

---

## 4. 优先实现计划

### Phase 1: Cron模块 (本周目标)
1. **jobs.py** - Job存储和CRUD
2. **scheduler.py** - 定时执行
3. **CLI集成** - cron命令

### Phase 2: Gateway增强
1. Webhook端点
2. 投递优化
3. 平台扩展

### Phase 3: CLI完善
1. cron完整命令
2. service管理
3. agent spawn

---

## 5. 实施建议

**从最小可用开始：**
1. 先实现jobs.py的核心功能
2. 创建scheduler.py的基础tick
3. 集成到现有cron命令

**分块实施（每次<300字符）：**
- Chunk 1: jobs.py基础结构
- Chunk 2: Schedule解析
- Chunk 3: Job CRUD
- Chunk 4: scheduler基础
- Chunk 5: CLI集成
