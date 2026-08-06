#!/usr/bin/env python3
"""康复验证：触发Mimir做写卡任务（P0修复后应真正落盘）"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """【康复测试】写一个简短的康复验证报告。

【任务】用write_file把以下内容写入 /home/rayliu/wiki/concepts/Mimir康复验证-20260805.md（绝对路径，禁止/tmp）：

# Mimir康复验证（2026-08-05）

P0修复后测试：verify guard现在区分调查与写盘，写盘任务必须有write_file调用才放行。

本次任务我执行了：write_file（本文件）→ 验证落盘。
康复状态：待Hermes确认。

【边界】只写这个文件，禁止stop/kill服务，禁止读其他文件（避免调查拖延）。
【验证】写完后用terminal stat确认文件存在，报告结果。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 康复验证：触发Mimir写卡...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=6, verbose=False)
    print(f"✅ 完成: {str(result)[:150]}")

if __name__ == "__main__":
    asyncio.run(main())
