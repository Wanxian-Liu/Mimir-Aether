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
