#!/usr/bin/env python3
"""P1-3 PiAgent 批次驱动：每轮 3 个 PiAgent 并行处理 3 个批次。

用法: python3 scripts/p1_3_pi_run.py <round>  (round=1 -> 批01-03, round=2 -> 批04-06, ...)
"""
import asyncio, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from subagent_bridge import _spawn_async

WIKI = os.environ.get("MIMIR_WIKI_ROOT", os.path.expanduser("~/wiki"))

PROMPT_TMPL = """你是 MimirAether 知识库（{wiki}）的 source 字段整理助手。SCHEMA 规范（{wiki}/SCHEMA.md）要求 concepts/discussions/comparisons 卡必须带**单数** source 字段（真实来源，禁止编造）。

处理清单（每行一个相对路径，相对于 wiki 根）：
{listing}

规则（按优先级）：
1. 先 read 每张卡（frontmatter + 正文），判断内容真实来源。
2. 卡内有 arXiv 编号（如 arXiv:2605.28781 或单独数字编号）→ source 用 https://arxiv.org/abs/<编号>（这是可构造的真实 URL，不算编造）。
3. 卡内有 http(s) URL → 取最有代表性的一个（arxiv / github / 官方文档 / 论文页优先）。
4. 正文提到 readings/books/ 或 raw/ 下的真实文件 → 用该相对路径（必须先 test -f {wiki}/<路径> 确认存在，不存在则不用）。
5. 卡是内部报告 / 执行记录 / 审计 / 讨论方案类 → 检查 discussions/ 或 concepts/ 下是否有真实存在的关联卡（test -f 确认后指向它）；也检查 raw/ 下是否有对应素材。
6. 全部找不到 → source: "待补raw"。
7. 若 frontmatter 用的是复数 `sources:` 字段 → 重命名为单数 `source:`，值同步校验（非 URL 且不存在的值删除或替换为合法值）。
8. 若已有单数 source 但值非法（机构名、不存在的路径、docs/ 开头）→ 从正文找真实来源替换。

字段写法：
- 单值: source: "<值>"
- 多值: source:
  - "<值1>"
  - "<值2>"

硬性要求：
- 只改 frontmatter 的 source/sources 字段，绝对不动正文和其他字段
- 本地路径 source 必须 test -f 验证通过才写
- 每张卡改完用 grep 或 read 确认字段落盘
- 禁止编造任何 URL / 路径

输出（stdout 最后一段，一行一张卡）：
<相对路径> | <动作: added/renamed/placeholder/fixed> | <source值>
最后一行: DONE"""


def build_prompt(files):
    listing = "\n".join(files)
    return PROMPT_TMPL.format(wiki=WIKI, listing=listing)


async def main():
    rnd = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    batch_files = [f"/tmp/p1_3_pi_batch_{rnd*3-2:02d}.json",
                   f"/tmp/p1_3_pi_batch_{rnd*3-1:02d}.json",
                   f"/tmp/p1_3_pi_batch_{rnd*3:02d}.json"]
    tasks = []
    for bf in batch_files:
        if not os.path.exists(bf):
            print(f"[skip] {bf} 不存在")
            continue
        files = json.load(open(bf, encoding="utf-8"))
        tasks.append(_spawn_async(
            type="general-purpose",
            prompt=build_prompt(files),
            timeout=900,
        ))
    if not tasks:
        print("无任务")
        return
    results = await asyncio.gather(*tasks)
    out = []
    for r in results:
        out.append({
            "success": r.success,
            "exit_code": r.exit_code,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "error": r.error,
        })
    path = f"/tmp/p1_3_pi_results_round{rnd}.json"
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for i, r in enumerate(results):
        print(f"=== 子代理{i+1}: success={r.success} exit={r.exit_code} ===")
        print((r.stdout or "")[:2500])
        if r.error:
            print("ERROR:", r.error)


if __name__ == "__main__":
    asyncio.run(main())
