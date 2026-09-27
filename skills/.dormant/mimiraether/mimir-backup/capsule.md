# [DORMANT] mimir-backup

**沉寂时间**: 2026-09-27T08:48:59.296114+00:00
**原始分类**: mimiraether
**描述**: 全量备份 MimirAether 系统状态。三层架构，每个 tgz 含 SHA256 校验和 + 随机文件提取完整性验证。
**触发阈值**: 60天未触碰

---

## 技能要点

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

### Step 

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimir-backup")` 即可自动唤醒。
