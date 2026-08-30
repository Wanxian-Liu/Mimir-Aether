#!/usr/bin/env python3
"""康复复验：guard默认启用后，Mimir写卡任务应被真正约束"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """【康复复验】写一段简短的双循环讨论复盘。

【任务】用write_file把以下内容写入 " + os.environ.get("MIMIR_WIKI_ROOT", os.path.expanduser("~/wiki")) + "/concepts/Mimir康复复验-双循环-20260805.md（绝对路径）：

# Mimir康复复验（双循环修复后）

guard_enabled默认改为1后，verify guard真正生效。

本次任务验证：guard会阻止"只调查不写盘"——本任务我执行write_file落盘。

【边界】只写这个文件，禁止读其他文件，禁止stop/kill。
【验证】写完后terminal stat确认，报告结果。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 康复复验：guard启用后Mimir写卡...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=6, verbose=False)
    print(f"✅ 完成: {str(result)[:150]}")

if __name__ == "__main__":
    asyncio.run(main())
