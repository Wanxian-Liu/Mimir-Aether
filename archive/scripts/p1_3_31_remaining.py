#!/usr/bin/env python3
"""P1-3.1 剩余 6 张卡 PiAgent 并行补 source（6 子代理 x 1 张）。"""
import asyncio, json, os, sys

sys.path.insert(0, "/home/rayliu/src/MimirAether")
from subagent_bridge import _spawn_async

RULE = """对这张卡：先 read_file 读全文，判断真实来源，只修改 frontmatter 的 source/sources 字段（不动正文和其他字段），最后 read_file 验证落盘。
source 溯源优先级：
1. 卡内 arXiv 编号 -> https://arxiv.org/abs/<编号>
2. 卡内 http(s) URL -> 取最有代表性的（过滤 127.0.0.1/localhost/example.com）
3. 正文提到的 readings/ 或 raw/ 真实文件 -> 相对路径（先 bash test -f 验证存在）
4. 内部执行/审计/方案卡 -> 检查 [[wikilink]] 或明确提到的 discussions/ concepts/ 关联卡（test -f 验证存在后指向它）
5. 全部找不到 -> source: "unknown"（诚实声明，禁止写"待补raw"或"unknown（待溯源）"占位）
字段写法：单值 source: "<值>"；多值 source:\\n  - "<值1>"\\n  - "<值2>"
禁止：编造任何 URL/路径；写"待补raw"/"unknown（待溯源）"占位。
输出（stdout 最后一行）：<相对路径> | <动作: added/renamed/fixed/unknown> | <source值>
最后一行: DONE"""

CARDS = [
    ("concepts/2026-08-11-整理方案-完整版.md", "source 是 '待补raw' 占位，正文有 wikilink。"),
    ("concepts/A1修复-截断与后置审计-20260805.md", "source 是 '待补raw' 占位，短卡。"),
    ("concepts/AGENTS执行纪律审计-20260809.md", "source 是 '待补raw' 占位，frontmatter 有 based_on 字段指向真实文件。"),
    ("concepts/Hermes-SOUL审计更新-20260805.md", "source 是 '待补raw' 占位，内部审计卡。"),
    ("concepts/Mimir-P1-1-source规范报告.md", "frontmatter 不完整（缺 title/created/updated/type/tags 等），source 是 'unknown（待溯源）' 占位，需补全基础字段并把 source 改为合法值。"),
    ("concepts/Mimir-P1-2-source统一报告.md", "frontmatter 不完整，source 是 'unknown（待溯源）' 占位，需补全基础字段并把 source 改为合法值。"),
]


def build_prompt(rel, hint):
    return (
        "你是 MimirAether 知识库（/home/rayliu/wiki）的 source 字段整理助手。\n"
        f"处理 1 张卡：{rel}\n"
        f"已知问题：{hint}\n"
        + RULE
    )


async def main():
    tasks = []
    for rel, hint in CARDS:
        tasks.append(_spawn_async(
            type="general-purpose",
            prompt=build_prompt(rel, hint),
            model="deepseek/deepseek-v4-flash",
            timeout=1200,
        ))
    results = await asyncio.gather(*tasks)
    out = []
    for i, r in enumerate(results, start=1):
        out.append({
            "card": CARDS[i-1][0],
            "success": r.success,
            "exit_code": r.exit_code,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "error": r.error,
        })
    json.dump(out, open("/tmp/p1_3_31_remaining_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for i, r in enumerate(results, start=1):
        print(f"=== 卡{i} {CARDS[i-1][0]}: success={r.success} exit={r.exit_code} ===", flush=True)
        print((r.stdout or "")[:1200], flush=True)
        if r.error:
            print("ERROR:", r.error, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
