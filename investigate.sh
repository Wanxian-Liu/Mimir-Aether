#!/usr/bin/env python3
import sys, asyncio
sys.path.insert(0, '.')
from agent.core_loop import MimirAetherAgent

async def main():
    agent = MimirAetherAgent()
    task = """调查为什么Mimicore生成的胶囊GDI分数只有0.5左右，无法达到70分。

请执行以下调查：
1. 查看gdi_scorer.py的实现，了解GDI评分算法
2. 查看capsule_generator.py，了解胶囊生成逻辑
3. 检查是否有配置参数影响评分
4. 分析现有胶囊的评分维度（confidence、success_streak、blast_radius等）

然后总结：
- GDI70分需要什么条件？
- 为什么现在只有0.5？
- 如何改进可以提高分数到70+？"""
    result = await agent.chat(task)
    print('=== 调查结果 ===')
    print(result)

asyncio.run(main())