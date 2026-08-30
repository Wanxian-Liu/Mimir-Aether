#!/usr/bin/env python3
"""强制Mimir写第2部分（上下文/压缩）体检段"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """立即完成"Mimir核心体检第2部分（上下文/压缩）"的讨论卡段落。

【任务】用write_file把这些内容**追加**到 " + os.environ.get("MIMIR_WIKI_ROOT", os.path.expanduser("~/wiki")) + "/discussions/Mimir核心体检-2上下文压缩.md 末尾（绝对路径，禁止/tmp）：

### Mimir（被体检对象·自省）—— 2026-08-05 亲写版

**1. 结构性bug（读自己context_compressor.py后）**：
[写你发现的bug，带行号——如压缩触发时机/阈值/保护缺失等]

**2. 对照Hermes**：
[你对照Hermes压缩器的发现]

**3. 严重度**：
[P0/P1/P2分级]

**4. 修复方案**：
[你的建议]

【边界】只追加到指定文件，不改其他段，禁止stop/kill，禁止写/tmp，禁止读其他文件。
【验证】写完后terminal grep "### Mimir" 确认落盘，报告结果。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 强制Mimir写第2部分体检段...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=8, verbose=False)
    print(f"✅ 完成: {str(result)[:150]}")

if __name__ == "__main__":
    asyncio.run(main())
