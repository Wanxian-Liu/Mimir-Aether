#!/usr/bin/env python3
import sys, asyncio
sys.path.insert(0, '.')
from agent.core_loop import MimirAetherAgent

async def main():
    agent = MimirAetherAgent()
    print("Testing run_conversation...")
    result = await agent.run_conversation("hello")
    print("run_conversation result type:", type(result))
    print("run_conversation result:", result)
    print()
    print("Testing chat...")
    result2 = await agent.chat("hello")
    print("chat result type:", type(result2))
    print("chat result:", result2)

asyncio.run(main())