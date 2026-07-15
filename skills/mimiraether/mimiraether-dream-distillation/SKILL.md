# 梦境记忆蒸馏操作手册

## 用途
手动触发或诊断梦境记忆蒸馏——将 persistent.json 中的记忆条目去重合并压缩。

## 检查蒸馏前的数据状态
```bash
python3 -c "
import json
with open('/home/rayliu/.mimiraether/data/persistent.json') as f:
    d = json.load(f)
mem = d.get('memory', {})
print('key_decisions:', len(mem.get('key_decisions', [])))
print('learned_patterns:', len(mem.get('learned_patterns', [])))
print('behavioral_constraints:', len(mem.get('behavioral_constraints', [])))
"
```

## 手动触发蒸馏
```bash
cd /home/rayliu/src/MimirAether
python3 -c "
import asyncio, sys
sys.path.insert(0, 'agent')
from dream_memory import run_dream_cycle
result = asyncio.run(run_dream_cycle(dry_run=False))
print(result)
"
```

## 验证蒸馏结果
同上 "检查蒸馏前的数据状态" 确认 key_decisions ≤ 20, learned_patterns ≤ 30。

## 已知问题
- 3 个 cron 任务（论文追踪、梦境蒸馏、每日提醒）全部注册但从未执行
- cron ticker 未激活导致定时任务不触发
- 当前的 workaround：手动触发

## 修复记录

### 2026-07-07: 两个 Python 语法 bug 修复
`_inject_api_key_from_proc()` 函数有两处 bug 导致模块无法被导入：

1. **Gateway PID 块缺少 for loop**（line 446）：`with open(p, "rb") as f: raw = f.read()` 后直接 `if entry.startswith(...)` 引用外层 `os.listdir` 的 `entry`。修复：加入 `for entry in raw.split(b"\\x00"):` 循环
2. **Fallback 扫描块缩进错误**（line 469）：`os.environ["DEEPSEEK_API_KEY"] = val` 多一层 4 空格缩进。修复：回退到与 `val = entry.split(...)` 同级

### 正确导入路径
执行 `execute_code` 沙盒中调用时，用 `sys.path.insert(0, REPO_ROOT)` 然后 `from agent.dream_memory import sync_run_dream_cycle`。
不要用 `sys.path.insert(0, 'agent')`——那会让 `agent/types.py` 遮蔽 Python 标准库 `types` 模块，导致循环导入崩溃。
