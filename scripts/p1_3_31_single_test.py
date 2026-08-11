#!/usr/bin/env python3
"""P1-3.1 单卡实测：pi 处理 1 张卡的耗时与成功率（terminal 真实环境）。"""
import asyncio, sys, time
sys.path.insert(0, "/home/rayliu/src/MimirAether")
from subagent_bridge import _spawn_async

PROMPT = """你是 wiki 知识库（/home/rayliu/wiki）的 source 字段整理助手。处理 1 张卡：
concepts/18bug修复执行记录.md

先 read_file /home/rayliu/wiki/concepts/18bug修复执行记录.md 读全文（frontmatter + 正文），判断真实来源，然后只修改 frontmatter 的 source 字段（不动正文和其他字段），最后 read_file 验证落盘。

source 溯源优先级：
1. 卡内 http(s) URL → 取最有代表性的（过滤 127.0.0.1/localhost/example.com）
2. 正文提到的 readings/ 或 raw/ 下真实文件 → 用相对路径（先 bash 执行 test -f /home/rayliu/wiki/<路径> 验证存在）
3. [[wikilink]] 指向的 concepts/discussions 关联卡（test -f 验证存在后指向它）
4. 都没有 → source: "unknown"（诚实声明，禁止写"待补raw"占位符）

字段写法：
- 单值: source: "<值>"

禁止：编造任何 URL/路径；写"待补raw"占位。
输出（stdout 最后一行）：<相对路径> | <动作: added/renamed/fixed/unknown> | <source值>
最后一行: DONE"""

t0 = time.time()
result = asyncio.run(_spawn_async(
    type="general-purpose",
    prompt=PROMPT,
    model="deepseek/deepseek-v4-flash",
    timeout=540,
))
dt = time.time() - t0
print(f"耗时: {dt:.0f}s  success={result.success} exit={result.exit_code}")
print("STDOUT:", (result.stdout or "")[:2000])
print("STDERR:", (result.stderr or "")[:500])
print("ERROR:", result.error)
