#!/usr/bin/env python3
"""Mimir 激活桥 v1——从Buzz收件箱读取任务并执行

流程：监听器收到@消息→写入收件箱→本桥读取最新任务→run_task执行
用法：python3 mimir-activator.py "任务内容"
"""
import sys, os, asyncio, json

def _inject_key():
    """从用户.env注入真key"""
    home = os.path.expanduser("~/.mimiraether")
    for line in open(os.path.join(home, ".env")):
        if line.startswith("DEEPSEEK_API_KEY="):
            os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
            break
    return os.environ.get("DEEPSEEK_API_KEY", "")

async def main():
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    if not task:
        print("用法: python3 mimir-activator.py '任务内容'")
        return 1

    key = _inject_key()
    print(f"🔑 key注入: 前缀{key[:5]} 长度{len(key)}")

    from mimir_cli.task_runner import run_task
    print(f"🎯 执行任务: {task[:60]}...")
    result = await run_task(
        task=task,
        model="deepseek-v4-flash",
        max_iterations=10,
        verbose=False,
    )
    print(f"✅ 完成，返回: {result}")
    return result

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
