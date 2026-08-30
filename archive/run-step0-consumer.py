#!/usr/bin/env python3
"""让Mimir执行第0步：消费方定义（戳它继续修复任务）"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """继续你的18bug修复任务（你之前已确认执行计划，现在完成第0步）。

你已读了源码（agent_loop.py / wm_voe_learning.py / 归档目录），确认了现场。现在执行：

【第0步：消费方定义】——把结论写入 ~/wiki/concepts/WM消费方定义.md

回答并落盘：
1. WM的surprise数据（surprise_events.jsonl / learned_surprises.json）给谁用？
   - 退化防护（degeneration_guard.surprise_gate）？预测改进？还是废弃？
2. 如果废弃——结论：停写+归档，不修P0三件
3. 如果保留——明确消费方，P0三件修复才有意义

用write_file写入：/home/rayliu/wiki/concepts/WM消费方定义.md
写完后用terminal验证（stat+cat确认落盘）。

这是修复任务的第一步，完成它。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 触发第0步：消费方定义...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=12, verbose=False)
    print(f"✅ 完成: {result}")

if __name__ == "__main__":
    asyncio.run(main())
