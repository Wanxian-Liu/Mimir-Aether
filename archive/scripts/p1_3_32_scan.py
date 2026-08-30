#!/usr/bin/env python3
"""P1-3.2 扫描：找出所有 source 仍为占位（待补raw / unknown（待溯源））的卡，
排除 P1-3.1 已处理的 21 张，输出候选清单（按目录分组，每目录内部按修改时间旧→新）。"""
import os, re, json

WIKI = "/home/rayliu/wiki"

# P1-3.1 已处理卡（run.py BATCHES 15 张 + remaining 6 张重叠 + 补源报告 2 张）
DONE = {
    "concepts/18bug修复执行记录.md",
    "concepts/1c-policy.md",
    "concepts/2026-08-11-整理方案-完整版.md",
    "concepts/A1修复-截断与后置审计-20260805.md",
    "concepts/AGENTS执行纪律审计-20260809.md",
    "concepts/AgencyAgent更新记录-20260805.md",
    "concepts/AgencyAgent角色使用规则-20260805.md",
    "concepts/Buzz四方cron配置-20260804.md",
    "concepts/Buzz接入进展报告-20260803.md",
    "concepts/Hermes-SOUL审计更新-20260805.md",
    "concepts/Loki审计模板-v2-9步执行清单.md",
    "concepts/Loki结构健康度自盯指标.md",
    "concepts/Mimir-P0工程记录-收益评估.md",
    "concepts/Mimir-P1-1-source规范报告.md",
    "concepts/Mimir-P1-2-source统一报告.md",
    "concepts/刘哥核心期望-token生存进化.md",
    "concepts/Mimir-SOUL修改方案-穷尽vs效率.md",
}

PLACEHOLDER_RE = re.compile(r"待补raw|unknown（待溯源）|unknown\(待溯源\)|待溯源")

def is_placeholder_source(path):
    """frontmatter 中 source/sources 字段含占位标记则返回 True。"""
    try:
        text = open(path, encoding="utf-8").read()
    except Exception:
        return False
    if not text.startswith("---"):
        return False
    lines = text.splitlines()
    end = None
    for i in range(1, min(len(lines), 60)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return False
    fm = "\n".join(lines[1:end])
    # 只在 source/sources 字段范围内检查
    in_src = False
    for line in lines[1:end]:
        if re.match(r"^sources?\s*:", line):
            in_src = True
            if PLACEHOLDER_RE.search(line):
                return True
            continue
        if re.match(r"^[a-z_]+:", line):
            in_src = False
            continue
        if in_src and PLACEHOLDER_RE.search(line):
            return True
    return False

def main():
    candidates = []
    for root, dirs, files in os.walk(WIKI):
        if ".git" in root or ".obsidian" in root or ".openclaw-wiki" in root:
            continue
        for fn in files:
            if not fn.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root, fn), WIKI)
            if rel in DONE:
                continue
            full = os.path.join(root, fn)
            if is_placeholder_source(full):
                mtime = os.path.getmtime(full)
                candidates.append((rel, mtime))
    # 按目录分组排序：concepts -> discussions -> entities -> comparisons -> readings -> raw
    def group_key(rel):
        d = rel.split("/")[0]
        order = {"concepts": 0, "discussions": 1, "entities": 2, "comparisons": 3,
                 "readings": 4, "raw": 5}
        return (order.get(d, 9), rel)
    candidates.sort(key=lambda x: (group_key(x[0]), x[1]))
    json.dump([{"rel": r, "mtime": m} for r, m in candidates],
              open("/tmp/p1_3_32_candidates.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"总候选（占位 source 且未处理）: {len(candidates)}")
    from collections import Counter
    c = Counter(r.split("/")[0] for r, _ in candidates)
    print("按目录:", dict(c))
    print("\n=== 前 40 张（按 目录->mtime 排序）===")
    for rel, m in candidates[:40]:
        print(f"  {rel}")

if __name__ == "__main__":
    main()
