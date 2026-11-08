#!/usr/bin/env python3
"""Mimir 激活桥 v1——从Buzz收件箱读取任务并执行

流程：监听器收到@消息→写入收件箱→本桥读取最新任务→run_task执行
用法：python3 mimir-activator.py "任务内容"
"""
import sys, os, asyncio, json

async def main():
    task = sys.argv[1] if len(sys.argv) > 1 else ""
    if not task:
        print("用法: python3 mimir-activator.py '任务内容'")
        return 1

    # 2026-11-08：删除自写 key 注入（原读用户 env 文件）。统一走 canonical loader。
    from mimir_cli.env_loader import load_hermes_dotenv
    load_hermes_dotenv()
    key = os.environ.get("DEEPSEEK_API_KEY", "")
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
