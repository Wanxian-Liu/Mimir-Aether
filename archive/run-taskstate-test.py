#!/usr/bin/env python3
"""task_state落地验证：Mimir跑写盘任务（WRITING状态应生效）"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """【task_state验证】写一个简短文件。

【任务】用write_file写入 /home/rayliu/wiki/concepts/task_state验证-20260805.md（绝对路径）：
# task_state验证
Mimir已接入TaskState（PROBING/WRITING/VERIFYING/DONE），nudge在WRITING时跳过。
本次任务验证task_state正常工作。

【边界】只写这个文件，禁止读其他文件。
【验证】写完后terminal stat确认。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 task_state验证任务...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=6, verbose=False)
    print(f"✅ 完成: {str(result)[:120]}")

if __name__ == "__main__":
    asyncio.run(main())
