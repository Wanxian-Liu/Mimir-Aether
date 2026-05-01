#!/usr/bin/env python3
"""
MimirAether独立服务
通过文件与主进程通信
"""
import sys
import os
sys.path.insert(0, '.')
# P0-3: 从环境变量读取API Key，不允许硬编码
api_key = os.environ.get('DEEPSEEK_API_KEY')
if not api_key:
    raise ValueError(
        "DEEPSEEK_API_KEY environment variable is not set. "
        "Please set it before running the service: "
        "export DEEPSEEK_API_KEY=your_key_here"
    )
os.environ['DEEPSEEK_API_KEY'] = api_key

import asyncio
import json
from pathlib import Path

COMM_FILE = "/tmp/mimiraether_command.txt"
RESULT_FILE = "/tmp/mimiraether_result.txt"

async def process_command(cmd: str) -> str:
    """处理命令"""
    from agent.core_loop import MimirAetherAgent
    
    agent = MimirAetherAgent()
    
    if cmd.startswith("chat:"):
        message = cmd[5:]
        result = await agent.chat(message)
        return result or "NO_RESULT"
    elif cmd.startswith("run:"):
        message = cmd[4:]
        result = await agent.run_conversation(message)
        return result or "NO_RESULT"
    elif cmd == "status":
        return "MimirAether running"
    else:
        return await agent.chat(cmd)

def main():
    print("MimirAether服务启动")
    
    while True:
        if Path(COMM_FILE).exists():
            with open(COMM_FILE, 'r') as f:
                cmd = f.read().strip()
            
            if cmd:
                print(f"收到命令: {cmd[:50]}...")
                try:
                    result = asyncio.run(process_command(cmd))
                    with open(RESULT_FILE, 'w') as f:
                        f.write(str(result)[:5000])
                except Exception as e:
                    with open(RESULT_FILE, 'w') as f:
                        f.write(f"ERROR: {e}")
                
                os.remove(COMM_FILE)
        
        import time
        time.sleep(1)

if __name__ == "__main__":
    main()