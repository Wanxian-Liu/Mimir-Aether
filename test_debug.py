#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/rayliu/.openclaw/projects/MimirAether')
print("Step 1: imports")

import asyncio
from agent.core_loop import MimirAetherAgent

print("Step 2: creating agent")
agent = MimirAetherAgent()

print("Step 3: calling agent.chat()")
result = agent.chat("hello")
print("Step 4: got coroutine, awaiting...")
final = asyncio.run(result)
print("Step 5: final result =", final)