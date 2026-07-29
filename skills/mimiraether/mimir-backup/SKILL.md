---
name: mimir-backup
description: 全量备份 MimirAether 系统状态。三层架构，每个 tgz 含 SHA256 校验和 + 随机文件提取完整性验证。
auto_load: false
---

# Mimir 全量备份技能

## 架构（学习 Hermes：备份非代码存档，不备份 git clone 可重建的内容）

| 层级 | 内容 | 典型大小 | 说明 |
|:---:|:----|:-------:|:----|
| **Tier 1 — 关键状态** | 身份文件(SOUL/AGENTS/USER/MEMORY + memory/日志) + .env + cron/ + state.db + persistent.json + gateway_state.json + checkpoints/ + ~/wiki/ | ~5MB | 空白机上即刻恢复独立运行所需 |
| **Tier 2 — 知识资产** | skills/ + evolution_backups/ | ~2MB | 恢复后依赖 Tier 1 |
| **Tier 3 — 会话历史** | data/sessions/ + sessions_search.db + chroma_sessions/ + retrospectives + causal_graph + 其他 data 文件 | ~30MB | 跨会话记忆恢复，重但不可丢弃 |

### 不备份
- `~/src/MimirAether/`（git clone 可重建）
- `logs/`（运行日志，非状态）
- `cache/` `audio_cache/` `image_cache/`（本地缓存，可重建）
- `sandboxes/`（临时工作区）

## 执行流程

### Step 1: 创建备份目录
```bash
mkdir -p ~/backups/mimir/$(date +%Y-%m-%d)
```

### Step 2: 打包三个 Tier（从 ~ 目录执行，用相对路径）
```bash
cd ~

# Tier 1 - 关键状态
tar czf ~/backups/mimir/$(date +%Y-%m-%d)/tier1-critical.tgz \
  --exclude='*/__pycache__' --exclude='*/*.pyc' \
  .mimiraether/SOUL.md .mimiraether/AGENTS.md .mimiraether/USER.md .mimiraether/MEMORY.md \
  .mimiraether/memory/ .mimiraether/.env .mimiraether/cron/ .mimiraether/state.db \
  .mimiraether/data/persistent.json .mimiraether/data/gateway_state.json .mimiraether/checkpoints/ \
  wiki/

# Tier 2 - 知识资产
tar czf ~/backups/mimir/$(date +%Y-%m-%d)/tier2-assets.tgz \
  --exclude='*/__pycache__' --exclude='*/*.pyc' \
  .mimiraether/skills/ .mimiraether/data/evolution_backups/

# Tier 3 - 会话历史
tar czf ~/backups/mimir/$(date +%Y-%m-%d)/tier3-sessions.tgz \
  --exclude='*/__pycache__' --exclude='*/*.pyc' \
  .mimiraether/data/sessions/ .mimiraether/data/sessions_search.db .mimiraether/data/chroma_sessions/ \
  .mimiraether/data/retrospectives.jsonl .mimiraether/data/causal_graph.json \
  .mimiraether/data/feedback_events.jsonl .mimiraether/data/monitor_alerts.json \
  .mimiraether/data/stock_portfolio.json .mimiraether/data/tool_quality.db* \
  .mimiraether/data/physics_fast_path.json .mimiraether/data/office-agent-cache.json .mimiraether/data/wm_phase0
```

### Step 3: 写 backup-manifest.json（SHA256 + 文件列表）
```bash
# 对每个 tgz 计算 sha256sum
# 写入 backup-manifest.json：备份日期、hostname、tiers 含 sha256+size、逐项内容清单
```

### Step 4: 验证完整性（随机提取文件）
```bash
# 从每个 tgz 随机提取一个文件确认内容可读
cd /tmp && tar xzf <tgz-path> .mimiraether/SOUL.md && head -5 .mimiraether/SOUL.md
```

## 已知陷阱
1. `.cron/` 目录名是 `cron/`（无前导点），不要写 `.cron/`
2. 多个命令同时运行时 tar 可能找不到同名目录（如 find 竞争 stat）
3. `wiki/` 在 home 目录下，不在 `.mimiraether/` 下
4. 每次备份后必须 run_ralph_tier0.sh 验证备份不破坏运行状态

## 恢复流程（未来用）
1. 解压 Tier 1 到干净 home：`tar xzf tier1-critical.tgz -C ~`
2. 解压 Tier 2：`tar xzf tier2-assets.tgz -C ~`
3. 解压 Tier 3：`tar xzf tier3-sessions.tgz -C ~`
4. git clone MimirAether 代码
5. 启动 Gateway 验证恢复

## 验证清单
- [ ] 三个 tgz 文件全部存在
- [ ] backup-manifest.json 含 SHA256
- [ ] 每个 tgz 至少随机提取 1 个文件验证内容完整性
- [ ] 总大小记录到 manifest
