#!/usr/bin/env python3
import sys, asyncio
sys.path.insert(0, '.')
from agent.core_loop import MimirAetherAgent

async def main():
    agent = MimirAetherAgent()
    task = """请修改文件 ~/.openclaw/projects/MimirAether/mimicore/gdi_scorer.py

找到第208-212行的代码：
```python
# 新胶囊基础分：如果有内容但没有任何使用记录，给0.3基础分
if content_len > 100:  # 有实质内容的新胶囊
    score = 0.3
```

把score = 0.3改成score = 0.7

完成后确认修改。"""
    result = await agent.chat(task)
    print('=== 结果 ===')
    print(result)

asyncio.run(main())