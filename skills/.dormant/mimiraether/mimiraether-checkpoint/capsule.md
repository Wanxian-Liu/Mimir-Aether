# [DORMANT] mimiraether-checkpoint

**沉寂时间**: 2026-07-14T18:58:40.561073+00:00
**原始分类**: mimiraether
**描述**: MimirAether检查点系统 - 基于Hermes实现的会话状态保存与恢复，支持文件系统快照、回滚和会话分支
**触发阈值**: 60天未触碰

---

## 技能要点

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
python mimiraether_checkpoint.py branch check

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-checkpoint")` 即可自动唤醒。
