#!/usr/bin/env python3
"""P1-3.2 二次补源：对 fix_file 标 unknown 但实际有线索（内联 related 列表 /
markdown 链接 [text](path.md)）的卡，改为指向真实存在的关联卡。

只改 frontmatter 的 source 字段；test -f 验证路径存在；找不到仍保持 unknown。
"""
import os, re, json

WIKI = "/home/rayliu/wiki"

CARDS = [
    "concepts/Mimir知识网-枢纽卡.md",
    "concepts/breakthrough-prize-kakeya.md",
    "concepts/WorldMonitor调研-20260805.md",
    "concepts/buzz-content-test.md",
    "concepts/evolution-knowledge-base-cross-domain-patterns.md",
    "concepts/Obsidian语义搜索-调研报告-20260805.md",
    "concepts/agent-self-healing-events.md",
    "concepts/Mimir-双写修复报告.md",
    "concepts/Mimir-delegate-bug修复报告.md",
    "concepts/Pi并行能力诊断-20260804.md",
    "concepts/Obsidian无法打开wiki的根因与修复-20260804.md",
    "concepts/Obsidian语义搜索-方案设计-20260805.md",
    "concepts/Obsidian语义搜索-落地完成-20260805.md",
    "concepts/WM消费方定义.md",
    "concepts/content-loop过滤误杀bug-20260805.md",
]


def find_existing_candidates(rel, text):
    """找真实存在的关联卡：内联 related 列表 + markdown 链接 + wikilink。"""
    cands = []
    seen = set()

    def add(p):
        p2 = p.replace("\\", "/")
        for prefix in ("", "concepts/", "discussions/", "entities/", "comparisons/"):
            cand = prefix + p2
            if not cand.endswith(".md"):
                cand += ".md"
            if cand == rel:
                continue
            if os.path.exists(os.path.join(WIKI, cand)) and cand not in seen:
                seen.add(cand)
                cands.append(cand)
                return True
        return False

    # 1. 内联 related: [a, b, c] 或 related: [x]
    for m in re.finditer(r"^related\s*:\s*\[([^\]]*)\]", text, re.M):
        for item in m.group(1).split(","):
            item = item.strip().strip('"').strip("'")
            if item:
                add(item)
    # 2. markdown 链接 [text](path.md) / [text](path)
    for m in re.finditer(r"\[[^\]]+\]\(([^)#]+?)(?:\.md)?\)", text):
        target = m.group(1).strip()
        if target.startswith("http") or target.startswith("#"):
            continue
        add(target)
    # 3. wikilink [[target]]
    for m in re.finditer(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text):
        add(m.group(1).strip())
    return cands[:4]


def fix_source(rel):
    path = os.path.join(WIKI, rel)
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        return {"file": rel, "action": "no-frontmatter", "source": None}
    lines = text.splitlines()
    end = None
    for i in range(1, min(len(lines), 60)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {"file": rel, "action": "no-frontmatter", "source": None}
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:])
    # 当前 source
    cur = None
    for l in fm_lines:
        if re.match(r"^source\s*:", l):
            cur = l.split(":", 1)[1].strip().strip('"').strip("'")
            break
    if cur and cur != "unknown" and not cur.startswith("待") and "unknown（" not in cur:
        return {"file": rel, "action": "keep", "source": cur}
    cands = find_existing_candidates(rel, text)
    if not cands:
        return {"file": rel, "action": "keep-unknown", "source": "unknown"}
    # 替换 frontmatter 中的 source 行（单行值）
    new_fm = []
    replaced = False
    for l in fm_lines:
        if re.match(r"^source\s*:", l) and not replaced:
            new_fm.append(f'source: "{cands[0]}"')
            replaced = True
        else:
            new_fm.append(l)
    if not replaced:
        new_fm.append(f'source: "{cands[0]}"')
    new_text = "---\n" + "\n".join(new_fm) + "\n---\n" + body
    open(path, "w", encoding="utf-8").write(new_text)
    # 验证
    verify = open(path, encoding="utf-8").read()
    ok = f'source: "{cands[0]}"' in verify.split("---", 2)[1] if verify.startswith("---") else False
    return {"file": rel, "action": "fixed", "source": cands[0], "verified": ok}


def main():
    results = []
    for rel in CARDS:
        r = fix_source(rel)
        results.append(r)
        print(f"{r['file']} | {r['action']} | {r.get('source')} | verified={r.get('verified')}")
    json.dump(results, open("/tmp/p1_3_32_pass2_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("DONE")


if __name__ == "__main__":
    main()
