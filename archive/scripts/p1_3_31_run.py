#!/usr/bin/env python3
"""P1-3.1 第一批 15 张卡 source 补齐 — PiAgent 并行驱动（3 批 × 5 卡）。

规则（用户 2026-08-12 指令）：
- 真溯源（卡内 URL/arXiv/真实本地路径/wikilink 或 web_search 外部来源）或诚实 unknown
- 禁止 "待补raw" 占位
- 只改 frontmatter 的 source/sources 字段，不动正文
- 本地路径必须 test -f 验证存在
"""
import json, os, sys

sys.path.insert(0, "/home/rayliu/src/MimirAether")
from subagent_bridge import spawn_multi

WIKI = "/home/rayliu/wiki"

RULE_TAIL = """
对每张卡：先 read_file 读全文（frontmatter + 正文），判断真实来源，然后只修改 frontmatter 的 source/sources 字段（绝对不动正文和其他字段），最后 read_file 验证落盘。

source 溯源优先级（从高到低）：
1. 卡内 arXiv 编号（如 arXiv:2605.28781）→ source 用 https://arxiv.org/abs/<编号>（真实可构造 URL，不算编造）
2. 卡内 http(s) URL → 取最有代表性的（arxiv/github/官方文档优先）；过滤 127.0.0.1/localhost/example.com 等垃圾地址
3. 正文提到的 readings/ 或 raw/ 下真实文件 → 用相对路径（必须先 terminal 执行 test -f /home/rayliu/wiki/<路径> 验证存在，不存在则不用）
4. 卡是内部执行记录/审计/方案类 → 检查正文 [[wikilink]] 或明确提到的 discussions/ concepts/ 关联卡（test -f 验证存在后指向它）
5. 若卡内容是外部知识（论文/技术主题）且以上都没有 → 用 web_search 搜索该主题找真实来源 URL，用搜索结果中真实存在的 URL
6. 全部找不到 → source: "unknown"（诚实声明，禁止写"待补raw"占位符）

字段写法：
- 单值: source: "<值>"
- 多值: source:
  - "<值1>"
  - "<值2>"

注意：这些是内部 wiki 卡（团队讨论/审计/执行记录），大多没有外部 URL 是正常的——诚实 unknown 优于编造。但若卡内提到真实存在的关联卡（test -f 验证），优先指向关联卡。

禁止：编造任何 URL/路径；写"待补raw"占位。

输出（stdout 最后一段，一行一张卡）：
<相对路径> | <动作: added/renamed/fixed/unknown> | <source值>
最后一行: DONE
"""

BATCHES = [
    # 批1：前 5 张
    """wiki 根目录: /home/rayliu/wiki（SCHEMA.md 定义 frontmatter 规范：source 必须是**单数**字段，禁止复数 sources）。
处理清单（每行一个相对路径，相对于 wiki 根）：
concepts/18bug修复执行记录.md
concepts/1c-policy.md
concepts/2026-08-11-整理方案-完整版.md
concepts/A1修复-截断与后置审计-20260805.md
concepts/AGENTS执行纪律审计-20260809.md

已知各卡问题：
1. 18bug修复执行记录.md → source 是 "待补raw" 占位，需替换。内部修复执行记录。
2. 1c-policy.md → 复数 sources 字段含坏值（IQ-EVO-43~45、docs/phase0/iqevo-1c-boundary.md——docs/ 开头的路径不是合法 source），需重命名为单数 source 并校验值。
3. 2026-08-11-整理方案-完整版.md → source 是 "待补raw" 占位，正文有 wikilink。
4. A1修复-截断与后置审计-20260805.md → source 是 "待补raw" 占位，短卡。
5. AGENTS执行纪律审计-20260809.md → source 出现两行重复的 "待补raw"，需合并为单数 source。""",
    # 批2：中间 5 张
    """wiki 根目录: /home/rayliu/wiki（SCHEMA.md 定义 frontmatter 规范：source 必须是**单数**字段，禁止复数 sources）。
处理清单（每行一个相对路径，相对于 wiki 根）：
concepts/AgencyAgent更新记录-20260805.md
concepts/AgencyAgent角色使用规则-20260805.md
concepts/Buzz四方cron配置-20260804.md
concepts/Buzz接入进展报告-20260803.md
concepts/Hermes-SOUL审计更新-20260805.md

已知各卡问题：
1. AgencyAgent更新记录-20260805.md → source 是 "待补raw" 占位；正文含 http URL（可用）。
2. AgencyAgent角色使用规则-20260805.md → source 是 "待补raw" 占位；内部角色规则卡。
3. Buzz四方cron配置-20260804.md → source 是 "待补raw" 占位；内部 cron 配置记录。
4. Buzz接入进展报告-20260803.md → source 是 "待补raw" 占位；正文含 http URL（可用）。
5. Hermes-SOUL审计更新-20260805.md → source 是 "待补raw" 占位；内部审计卡。""",
    # 批3：后 5 张
    """wiki 根目录: /home/rayliu/wiki（SCHEMA.md 定义 frontmatter 规范：source 必须是**单数**字段，禁止复数 sources）。
处理清单（每行一个相对路径，相对于 wiki 根）：
concepts/Loki审计模板-v2-9步执行清单.md
concepts/Loki结构健康度自盯指标.md
concepts/Mimir-P0工程记录-收益评估.md
concepts/Mimir-P1-1-source规范报告.md
concepts/Mimir-P1-2-source统一报告.md

已知各卡问题：
1. Loki审计模板-v2-9步执行清单.md → source 是 "待补raw" 占位；内部审计模板。
2. Loki结构健康度自盯指标.md → source 是 "待补raw" 占位；内部指标卡。
3. Mimir-P0工程记录-收益评估.md → source 是 "待补raw" 占位；内部工程记录。
4. Mimir-P1-1-source规范报告.md → frontmatter 不完整（缺 title/created/updated/type/tags 等字段），source 是 "unknown（待溯源）"，需补全 frontmatter 基础字段（title/created/updated/type/tags 从正文推断）并把 source 改为合法值。
5. Mimir-P1-2-source统一报告.md → frontmatter 不完整，source 是 "unknown（待溯源）"，需补全 frontmatter 基础字段并把 source 改为合法值。""",
]


def main():
    tasks = []
    for i, listing in enumerate(BATCHES, start=1):
        prompt = (
            "你是 MimirAether 知识库（/home/rayliu/wiki）的 source 字段整理助手。\n\n"
            + listing
            + "\n\n"
            + RULE_TAIL
        )
        tasks.append({
            "type": "general-purpose",
            "prompt": prompt,
            "model": "deepseek/deepseek-v4-flash",
        })
    print(f"[P1-3.1] 启动 {len(tasks)} 个 PiAgent 并行（flash 模型）...", flush=True)
    results = spawn_multi(tasks, parallel=True)
    out = []
    for i, r in enumerate(results, start=1):
        out.append({
            "batch": i,
            "success": r.success,
            "exit_code": r.exit_code,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "error": r.error,
            "model": r.model,
        })
    json.dump(out, open("/tmp/p1_3_31_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for i, r in enumerate(results, start=1):
        print(f"=== 批{i}: success={r.success} exit={r.exit_code} ===", flush=True)
        print((r.stdout or "")[:3000], flush=True)
        if r.error:
            print("ERROR:", r.error, flush=True)


if __name__ == "__main__":
    main()
