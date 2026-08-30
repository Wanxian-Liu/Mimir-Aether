#!/usr/bin/env python3
"""P1-3.2 下一批 15 张卡 source 补齐 — 确定性规则（复用 p1_3_31_fix.fix_file）。

批次选择：concepts 目录下 mtime 旧→新、未处理、非 P1-3 报告卡的前 15 张。
规则（用户 2026-08-12）：
- 真溯源（卡内 URL/arXiv/真实本地路径/wikilink，test -f 验证）或诚实 unknown
- 禁止 "待补raw" / "unknown（待溯源）" 占位
- 只改 frontmatter 的 source/sources 字段，不动正文与其他字段

用法: python3 scripts/p1_3_32_fix.py <batch_index 0|1|2>
"""
import importlib.util, json, sys

WIKI = "/home/rayliu/wiki"

# 加载 p1_3_31_fix 模块复用 fix_file
spec = importlib.util.spec_from_file_location(
    "p1_3_31_fix", "/home/rayliu/src/MimirAether/scripts/p1_3_31_fix.py")
p131 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p131)
fix_file = p131.fix_file

BATCHES = [
    [
        "concepts/Mimir-delegate-bug修复报告.md",
        "concepts/Mimir-双写修复报告.md",
        "concepts/Mimir知识网-枢纽卡.md",
        "concepts/Obsidian无法打开wiki的根因与修复-20260804.md",
        "concepts/Obsidian语义搜索-方案设计-20260805.md",
    ],
    [
        "concepts/Obsidian语义搜索-落地完成-20260805.md",
        "concepts/Obsidian语义搜索-调研报告-20260805.md",
        "concepts/Pi并行能力诊断-20260804.md",
        "concepts/WM消费方定义.md",
        "concepts/WorldMonitor调研-20260805.md",
    ],
    [
        "concepts/agent-self-healing-events.md",
        "concepts/breakthrough-prize-kakeya.md",
        "concepts/buzz-content-test.md",
        "concepts/content-loop过滤误杀bug-20260805.md",
        "concepts/evolution-knowledge-base-cross-domain-patterns.md",
    ],
]


def main():
    batch_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    results = []
    for rel in BATCHES[batch_idx]:
        r = fix_file(rel)
        results.append(r)
        print(f"{r['file']} | {r['action']} | {r.get('source')} | verified={r.get('verified')}")
    json.dump(results, open(f"/tmp/p1_3_32_batch{batch_idx}_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("DONE")


if __name__ == "__main__":
    main()
