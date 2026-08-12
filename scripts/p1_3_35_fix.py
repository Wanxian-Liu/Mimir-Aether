#!/usr/bin/env python3
"""P1-3.5 source 补齐 — 确定性脚本（复用 p1_3_31_fix.fix_file + pass2 规则，同 P1-3.4）。

批次：discussions 真占位 86 张中 mtime 旧->新前 15 张。
规则（用户 2026-08-12，同 P1-3.2 / P1-3.3 / P1-3.4）：
- 真溯源（卡内 URL/arXiv/真实本地路径/wikilink/related/markdown链接，test -f 验证）或诚实 unknown
- 禁止 "待补raw" / "unknown（待溯源）" 占位
- 只改 frontmatter 的 source/sources 字段，不动正文与其他字段
- 每张处理后立即 read back 验证

用法: python3 scripts/p1_3_35_fix.py
"""
import importlib.util, json, os, re

WIKI = "/home/rayliu/wiki"

# 加载 p1_3_31_fix 复用 fix_file / find_candidates
spec = importlib.util.spec_from_file_location(
    "p1_3_31_fix", "/home/rayliu/src/MimirAether/scripts/p1_3_31_fix.py")
p131 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p131)
fix_file = p131.fix_file

# 目标卡：discussions 前 15 张（mtime 旧->新，2026-08-12 p1_3_35_scan 确认）
CARDS = [
    "discussions/Mimir-P0执行报告-自我审计.md",
    "discussions/MimirGateway身份矛盾调查.md",
    "discussions/Mimir不落盘-架构根因深挖.md",
    "discussions/Mimir体检-C1效果验证.md",
    "discussions/Mimir原子整改清单-四方逐项投票.md",
    "discussions/Mimir双循环架构-根因与修复.md",
    "discussions/Mimir可靠性专项-四方会诊.md",
    "discussions/Mimir向Hermes学习-实验讨论.md",
    "discussions/Mimir学Hermes-第一学习点选定.md",
    "discussions/Mimir学习成果审视-四方会议.md",
    "discussions/Mimir整改B组-四方讨论.md",
    "discussions/Mimir整改C组-机制修复四方讨论.md",
    "discussions/Mimir整改二次讨论-执行前验证.md",
    "discussions/Mimir整改执行记录.md",
    "discussions/Mimir核心体检-1循环执行.md",
]


def pass2(rel):
    """pass2：fix_file 标 unknown 但有 related 列表 / markdown 链接 / wikilink 时改指真实关联卡。"""
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
    fm = "\n".join(fm_lines)
    body = "\n".join(lines[end + 1:])
    cur = None
    for l in fm_lines:
        if re.match(r"^source\s*:", l):
            cur = l.split(":", 1)[1].strip().strip('"').strip("'")
            break
    if cur and cur != "unknown" and not cur.startswith("待") and "unknown（" not in cur:
        return {"file": rel, "action": "keep", "source": cur}

    # 1. 复用 p1_3_31_fix 的候选提取（URL/arXiv/本地路径/wikilink，path_exists 验证）
    cands = p131.find_candidates(rel, text, fm)
    if not cands:
        # 2. 内联 related: [a, b, c]
        for m in re.finditer(r"^related\s*:\s*\[([^\]]*)\]", text, re.M):
            for item in m.group(1).split(","):
                item = item.strip().strip('"').strip("'")
                if not item:
                    continue
                p2 = item.replace("\\", "/")
                for prefix in ("", "concepts/", "discussions/", "entities/", "comparisons/"):
                    cand = prefix + p2
                    if not cand.endswith(".md"):
                        cand += ".md"
                    if cand != rel and os.path.exists(os.path.join(WIKI, cand)):
                        cands.append(cand)
                        break
    # 3. markdown 链接 [text](path.md)
    if not cands:
        for m in re.finditer(r"\[[^\]]+\]\(([^)#]+?)(?:\.md)?\)", text):
            tgt = m.group(1).strip()
            if tgt.startswith("http") or tgt.startswith("#"):
                continue
            p2 = tgt.replace("\\", "/")
            for prefix in ("", "concepts/", "discussions/", "entities/", "comparisons/"):
                cand = prefix + p2
                if not cand.endswith(".md"):
                    cand += ".md"
                if cand != rel and os.path.exists(os.path.join(WIKI, cand)):
                    cands.append(cand)
                    break
    if not cands:
        return {"file": rel, "action": "keep-unknown", "source": "unknown"}

    src = cands[0]
    new_fm = []
    replaced = False
    for l in fm_lines:
        if re.match(r"^source\s*:", l) and not replaced:
            new_fm.append(f'source: "{src}"')
            replaced = True
        else:
            new_fm.append(l)
    if not replaced:
        new_fm.append(f'source: "{src}"')
    new_text = "---\n" + "\n".join(new_fm) + "\n---\n" + body
    open(path, "w", encoding="utf-8").write(new_text)
    # read back 验证
    verify = open(path, encoding="utf-8").read()
    ok = f'source: "{src}"' in verify.split("---", 2)[1] if verify.startswith("---") else False
    return {"file": rel, "action": "fixed", "source": src, "verified": ok}


def main():
    results = []
    for rel in CARDS:
        r = fix_file(rel)
        if r.get("action") in ("keep-unknown", "keep", "no-frontmatter", "unknown"):
            r2 = pass2(rel)
            if r2.get("action") == "fixed":
                r = r2
        results.append(r)
        print(f"{r['file']} | {r['action']} | {r.get('source')} | verified={r.get('verified')}")
    json.dump(results, open("/tmp/p1_3_35_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(r["action"] for r in results)
    print("\n统计:", dict(c))
    print("DONE")


if __name__ == "__main__":
    main()
