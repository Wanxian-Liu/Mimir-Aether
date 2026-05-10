# MimirAether 心跳基座

## 架构

```
heartbeat/
├── beat.sh                 # 入口脚本（硬心跳 + 可选快照）
├── hard_beat.sh            # 硬心跳 — cron 每5分钟触发
├── soft_beat.py            # 软心跳 — 工具调用后记录
├── log_beat.py             # 软心跳包装器（自动间隔快照）
├── capability_snapshot.py  # 能力快照 — 5项关键能力扫描
├── logs/
│   ├── hard_beat.log       # 硬心跳日志
│   ├── soft_beat.log       # 软心跳日志
│   └── capability_snapshot.log  # 能力快照日志
└── backups/                # 修改前备份原文件
```

## 三层心跳

### 1. 硬心跳 (Hard Beat)
- **触发**: cron 每5分钟
- **内容**: 时间戳 + 进程数 + 磁盘用量 + Hermes进程状态
- **文件**: `logs/hard_beat.log`
- **手动**: `bash heartbeat/hard_beat.sh`

### 2. 软心跳 (Soft Beat)
- **触发**: 每次工具调用后手动调用
- **内容**: 工具名 + 耗时(ms) + 状态
- **文件**: `logs/soft_beat.log`
- **手动**: `python3 heartbeat/log_beat.py <tool> <ms> <status> [detail]`

### 3. 能力快照 (Capability Snapshot)
- **触发**: 手动或每50次工具调用自动
- **扫描**: skill_view / skill_manage / produce_capsule / session_search / 根源调试
- **文件**: `logs/capability_snapshot.log`
- **手动**: `python3 heartbeat/capability_snapshot.py`

## 回滚机制

如果心跳运行后出现异常（工具变慢、响应卡顿）：
1. 删除整个 `heartbeat/` 目录
2. 从 `heartbeat/backups/` 恢复被修改的原文件（如有）
3. 重启会话

## 使用方式

```bash
# 完整心跳（硬心跳 + 能力快照）
./heartbeat/beat.sh --snapshot

# 仅硬心跳
./heartbeat/beat.sh

# 记录一次工具调用
python3 heartbeat/log_beat.py read_file 1234 OK

# 手动能力快照
python3 heartbeat/capability_snapshot.py
```
