---
description: MimirAether检查点系统 - 基于Hermes实现的会话状态保存与恢复，支持文件系统快照、回滚和会话分支
---

# MimirAether Checkpoint System

## 描述

MimirAether检查点系统 - 基于Hermes实现的会话状态保存与恢复。支持文件系统快照、回滚、和会话分支。

**参考实现**: Hermes Agent checkpoint系统 (`hermes chat --checkpoints`, `/rollback`)

## 核心功能

- **状态快照**: 保存当前对话上下文、工具状态和内存到指定检查点
- **回滚恢复**: 从检查点恢复完整的会话状态
- **会话分支**: 创建当前会话的分支，支持并行探索不同方案
- **检查点列表**: 列出所有可用的检查点及其时间戳
- **差异比较**: 比较两个检查点之间的差异
- **清理管理**: 删除旧检查点以节省存储空间

## 使用场景

- 长时间任务中断后继续
- 尝试不同方案前的状态备份
- 会话回溯和问题诊断
- A/B测试不同的解决方案
- 危险操作前的状态保护

## 存储位置

```
~/.mimiraether/checkpoints/       # 检查点数据
├── metadata.json                 # 检查点索引
├── snapshots/                    # 快照存储
│   ├── checkpoint_001/           # 快照1
│   │   ├── context.json          # 对话上下文
│   │   ├── memory.json           # 记忆数据
│   │   ├── tools_state.json      # 工具状态
│   │   └── timestamp.txt         # 创建时间
│   └── checkpoint_002/           # 快照2...
```

## Python API

```python
from mimiraether_checkpoint import CheckpointManager

# 初始化管理器
cm = CheckpointManager(base_dir="~/.mimiraether/checkpoints")

# 创建检查点
cp = cm.create_checkpoint(
    label="before_refactor",
    context={"messages": [...], "system": "..."},
    memory={"user_prefs": {...}},
    tools_state={"terminal": {...}, "files": {...}}
)
print(f"Created: {cp.id}")

# 列出检查点
for cp in cm.list_checkpoints():
    print(f"[{cp.id}] {cp.label} - {cp.created_at}")

# 回滚到检查点
restored = cm.rollback(cp.id)
print(f"Restored {len(restored['messages'])} messages")

# 分支会话
branch = cm.branch_from_checkpoint(
    source_id="checkpoint_001",
    branch_label="explore_alternative"
)
print(f"Branch created: {branch.id}")

# 比较检查点
diff = cm.diff("checkpoint_001", "checkpoint_002")
print(diff)

# 清理旧检查点
cm.cleanup(max_snapshots=10)
```

## CLI 接口

```bash
# 创建检查点
python mimiraether_checkpoint.py create --label "before_refactor"

# 列出检查点
python mimiraether_checkpoint.py list

# 查看检查点详情
python mimiraether_checkpoint.py show checkpoint_003

# 回滚到检查点
python mimiraether_checkpoint.py rollback checkpoint_003

# 创建分支
python mimiraether_checkpoint.py branch checkpoint_003 --label "try_alternative"

# 比较两个检查点
python mimiraether_checkpoint.py diff checkpoint_001 checkpoint_002

# 清理（保留最近N个）
python mimiraether_checkpoint.py cleanup --keep 5

# 删除单个检查点
python mimiraether_checkpoint.py delete checkpoint_003
```

## 检查点数据结构

```json
{
  "id": "cp_20260428_143052_a1b2c3",
  "label": "before_refactor",
  "created_at": "2026-04-28T14:30:52Z",
  "parent_id": null,
  "branch_name": "main",
  "metadata": {
    "message_count": 42,
    "token_estimate": 12000,
    "files_modified": ["src/auth.py", "tests/test_auth.py"]
  },
  "context": {
    "messages": [...],
    "system_prompt": "...",
    "model": "claude-sonnet-4"
  },
  "memory": {
    "short_term": {...},
    "long_term": {...}
  },
  "tools_state": {
    "terminal": {"cwd": "/project", "env": {...}},
    "files": {...}
  }
}
```

## 与Hermes集成

Hermes原生支持检查点功能：

```bash
# 启用检查点
hermes chat --checkpoints

# 会话内回滚
/rollback          # 回滚到上一个检查点
/rollback 3       # 回滚到3个检查点之前
/rollback <name>   # 回滚到指定检查点

# 会话分支
/branch           # 创建当前会话的分支
/fork             # 同上
```

### Hermes检查点配置

```yaml
# $MIMIR_AETHER_HOME/config.yaml（或开发时仓库根 `config.yaml`）
checkpoints:
  enabled: true
  max_snapshots: 50  # 保留的最大快照数
```

## 最佳实践

1. **定期创建**: 在完成重要里程碑后创建检查点
2. **标签清晰**: 使用描述性标签便于识别
3. **不过度保留**: 设置合理的max_snapshots限制
4. **分支探索**: 使用分支尝试不同方案，主分支保持稳定
5. **清理旧点**: 定期清理已验证无用的检查点

## 实现类参考

```python
@dataclass
class Checkpoint:
    id: str
    label: str
    created_at: str
    parent_id: Optional[str]
    branch_name: str
    metadata: dict
    context: dict
    memory: dict
    tools_state: dict

class CheckpointManager:
    def __init__(self, base_dir: str = "~/.mimiraether/checkpoints")
    def create_checkpoint(self, label: str, **snapshot_data) -> Checkpoint
    def rollback(self, checkpoint_id: str) -> dict
    def branch_from_checkpoint(self, source_id: str, branch_label: str) -> Checkpoint
    def list_checkpoints(self, branch: str = None) -> List[Checkpoint]
    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint
    def delete_checkpoint(self, checkpoint_id: str) -> bool
    def diff(self, id1: str, id2: str) -> dict
    def cleanup(self, max_snapshots: int = 50) -> int
```
