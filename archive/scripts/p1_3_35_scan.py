#!/usr/bin/env python3
"""P1-3.5 scan 修正版 — 精确提取 frontmatter source 字段（含多行 list 格式），
只把真占位（待补raw / unknown（待溯源）/ 空 / 缺失）算占位。"""
import os, re, json, datetime

WIKI = "/home/rayliu/wiki"
DISC = os.path.join(WIKI, "discussions")

# 非知识卡（任务派发/信号/报告卡自身，不在 P1-3 范围）
EXCLUDE = {
    "discussions/2026-08-12-Hermes派发-P1-3.5.md",
    "discussions/2026-08-12-Hermes派发-P1-3.4.md",
    "discussions/2026-08-12-Mimir-P1-3.4-@hermes信号.md",
    "discussions/2026-08-12-Mimir-P1-3.3-@hermes信号.md",
    "discussions/2026-08-12-Mimir-P1-3.2-@hermes信号.md",
    "discussions/2026-08-12-Mimir-P1-3-source补齐-@hermes信号.md",
    "discussions/P1-2-source统一报告-@hermes信号卡.md",
    "discussions/2026-08-12-Mimir-P1-2-source统一-@hermes信号.md",
    "discussions/Mimir-P1-3-source补齐报告.md",
    "discussions/Mimir-P1-3-source补源报告.md",
}


def extract_source(text):
    """返回 (source_raw, is_placeholder)。支持单行 source: x 与多行 list。"""
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
    # 找 source/sources 字段（含多行 list 值）
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
                # 空行或缩进续行
                if l.strip():
                    vals.append(l.strip())
    if not vals:
        return None, True  # 无 source 字段 = 占位
    joined = " ".join(vals)
    placeholder = bool(re.search(r"待补raw|unknown（待溯源）|unknown\(待溯源\)|待溯源|占位", joined))
    return joined, placeholder


def main():
    cards = []
    for fn in sorted(os.listdir(DISC)):
        if not fn.endswith(".md"):
            continue
        rel = f"discussions/{fn}"
        if rel in EXCLUDE:
            continue
        path = os.path.join(DISC, fn)
        text = open(path, encoding="utf-8").read()
        src_raw, is_ph = extract_source(text)
        if is_ph:
            mtime = os.path.getmtime(path)
            cards.append((mtime, rel, src_raw))

    cards.sort(key=lambda x: x[0])
    print(f"真占位卡总数: {len(cards)}")
    for i, (mt, rel, sv) in enumerate(cards, 1):
        ts = datetime.datetime.fromtimestamp(mt).strftime("%m-%d %H:%M")
        print(f"{i:3d} | {ts} | {rel} | source={sv}")
    print("\n=== 前 15 张（本批）===")
    for mt, rel, sv in cards[:15]:
        print(rel)
    json.dump([{"mtime": mt, "rel": rel, "source": sv} for mt, rel, sv in cards],
              open("/tmp/p1_3_35_scan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
