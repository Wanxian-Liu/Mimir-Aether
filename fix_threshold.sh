#!/usr/bin/env python3
import sys, asyncio
sys.path.insert(0, '.')
from agent.core_loop import MimirAetherAgent

async def main():
    agent = MimirAetherAgent()
    task = """请执行以下两个任务：

1. 找到Mimicore中GDI阈值的配置（应该是某个文件中的0.7或70），把它改成0.6
2. 查看是哪里有60秒超时的限制，确认这个timeout的来源

完成后报告你做了什么修改。"""
    result = await agent.chat(task)
    print('=== 执行结果 ===')
    print(result)

asyncio.run(main())