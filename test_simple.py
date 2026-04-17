#!/usr/bin/env python3
import sys, asyncio
sys.path.insert(0, '.')
from agent.core_loop import MimirAetherAgent

async def main():
    agent = MimirAetherAgent()
    result = await agent.chat('say hello in 10 words')
    print('结果:', result)

asyncio.run(main())