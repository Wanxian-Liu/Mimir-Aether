#!/usr/bin/env python3
"""A7/P1-3.6 scan — 精确提取 discussions + entities 的 frontmatter source 字段，
分类：真占位（待补raw / unknown（待溯源）/ 待溯源 / 占位 / 空 / 缺失）vs 真 source。
输出逐卡清单 + 统计。"""
import os, re, sys, json

WIKI = "/home/rayliu/wiki"
DIRS = ["discussions", "entities"]
# 非知识卡（任务派发/信号/报告卡自身，不在 A7/P1-3 范围）
EXCLUDE = {
    "discussions/2026-08-12-Hermes派发-P1-3.5.md",
    "discussions/2026-08-12-Hermes派发-P1-3.4.md",
    "discussions/2026-08-12-Hermes派发-P1-3.6.md",
    "discussions/2026-08-12-Mimir-P1-3.4-@hermes信号.md",
    "discussions/2026-08-12-Mimir-P1-3.3-@hermes信号.md",
    "discussions/2026-08-12-Mimir-P1-3.2-@hermes信号.md",
    "discussions/2026-08-12-Mimir-P1-3-source补齐-@hermes信号.md",
    "discussions/P1-2-source统一报告-@hermes信号卡.md",
    "discussions/2026-08-12-Mimir-P1-2-source统一-@hermes信号.md",
    "discussions/Mimir-P1-3-source补齐报告.md",
    "discussions/Mimir-P1-3-source补源报告.md",
    "discussions/todo与遗留问题四方讨论.md",
    "discussions/RAW统一方案四方讨论.md",
    "discussions/Mimir容量与行为改革四方讨论.md",
    "discussions/2026-08-12-Mimir-P1-3.5-@hermes信号.md",
    "discussions/2026-08-12-Mimir-A1压缩启用-@hermes信号.md",
    "discussions/2026-08-12-Mimir-A3-max_turns分档-@hermes信号.md",
    "discussions/2026-08-12-Mimir-A4-规则架构审计-@hermes信号.md",
    "discussions/2026-08-12-Hermes巡游-A4执行中-todo运行时修复未生效.md",
    "discussions/2026-08-12-Mimir-修todo工具接线bug-@hermes信号.md",
}

PLACEHOLDER_RE = re.compile(r"待补raw|unknown（待溯源）|unknown\(待溯源\)|待溯源|占位|TBD|待补")


def extract_source(text):
    """返回 (source_raw, is_placeholder)。"""
    if not text.startswith("---"):
        return None, True
    lines = text.splitlines()
    end = None
    for i in range(1, min(len(lines), 60)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, True
    fm_lines = lines[1:end]
    vals = []
    in_src = False
    for l in fm_lines:
        if re.match(r"^sources?\s*:", l):
            in_src = True
            rest = l.split(":", 1)[1].strip()
            if rest:
                vals.append(rest)
            continue
        if in_src:
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\s*:", l):
                in_src = False
            elif l.strip().startswith("-"):
                vals.append(l.strip()[1:].strip())
            else:
                if l.strip():
                    vals.append(l.strip())
    if not vals:
        return None, True
    joined = " ".join(vals)
    placeholder = bool(PLACEHOLDER_RE.search(joined))
    return joined, placeholder


def main():
    cards = []
    for d in DIRS:
        full = os.path.join(WIKI, d)
        if not os.path.isdir(full):
            continue
        for fn in sorted(os.listdir(full)):
            if not fn.endswith(".md"):
                continue
            rel = f"{d}/{fn}"
            if rel in EXCLUDE:
                continue
            p = os.path.join(full, fn)
            try:
                text = open(p, encoding="utf-8").read()
            except Exception as e:
                cards.append({"file": rel, "error": str(e)})
                continue
            src, ph = extract_source(text)
            mtime = os.path.getmtime(p)
            cards.append({
                "file": rel, "source": src, "placeholder": ph,
                "mtime": mtime, "size": len(text),
            })

    placeholders = [c for c in cards if c.get("placeholder")]
    real = [c for c in cards if not c.get("placeholder") and not c.get("error")]
    no_fm = [c for c in cards if c.get("source") is None]

    print(f"=== 扫描范围: {WIKI}/{{discussions,entities}} ===")
    print(f"总卡数: {len(cards)}")
    print(f"真 source: {len(real)}")
    print(f"占位卡: {len(placeholders)}")
    print()
    print("=== 占位卡逐卡清单（mtime 旧→新）===")
    for c in sorted(placeholders, key=lambda x: x["mtime"]):
        import datetime
        mt = datetime.datetime.fromtimestamp(c["mtime"]).strftime("%m-%d %H:%M")
        print(f"  [{mt}] {c['file']}")
        print(f"      source={repr(c['source'])}")
    print()
    print("=== 统计 ===")
    from collections import Counter
    by_dir = Counter(c["file"].split("/")[0] for c in placeholders)
    print(f"占位按目录: {dict(by_dir)}")
    # 打印无 frontmatter 卡（若有）
    if no_fm:
        print(f"无 frontmatter: {len(no_fm)}")
        for c in no_fm:
            print(f"  {c['file']}")


if __name__ == "__main__":
    main()
