#!/usr/bin/env python3
"""P1-3.4 source 补齐 — 确定性脚本（复用 p1_3_31_fix.fix_file + p1_3_33 的 pass2 规则）。

批次：discussions 占位 102 张中 mtime 旧->新前 15 张。
规则（用户 2026-08-12，同 P1-3.2 / P1-3.3）：
- 真溯源（卡内 URL/arXiv/真实本地路径/wikilink/related/markdown链接，test -f 验证）或诚实 unknown
- 禁止 "待补raw" / "unknown（待溯源）" 占位
- 只改 frontmatter 的 source/sources 字段，不动正文与其他字段
- 每张处理后立即 read back 验证

用法: python3 scripts/p1_3_34_fix.py
"""
import importlib.util, json, os, re

WIKI = "/home/rayliu/wiki"

# 加载 p1_3_31_fix 复用 fix_file / find_candidates
spec = importlib.util.spec_from_file_location(
    "p1_3_31_fix", "/home/rayliu/src/MimirAether/scripts/p1_3_31_fix.py")
p131 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p131)
fix_file = p131.fix_file

# 目标卡：discussions 前 15 张（mtime 旧->新，2026-08-12 scan 确认）
CARDS = [
    "discussions/C1门禁v6审计-Mimir活体测试.md",
    "discussions/GraphRAG7篇读后-OpenClaw使用方案.md",
    "discussions/GraphRAG7篇读后-四方使用方案-总体总结.md",
    "discussions/GraphRAG7篇读后-四方聚焦讨论-原子化.md",
    "discussions/GraphRAG论文四方精读-7篇总收束.md",
    "discussions/Heartbeat讨论室机制完善.md",
    "discussions/LLM Wiki论文研讨-四方各挑一篇投票.md",
    "discussions/Loki-Mimir-subprocess修复方案投票.md",
    "discussions/Loki四方微信双断连-四方紧急讨论.md",
    "discussions/Loki的Wiki写入能力验证.md",
    "discussions/ML知识迁移wiki-四方讨论.md",
    "discussions/Mimir-Harness方案讨论-与Hermes差距分析与完善方向.md",
    "discussions/Mimir-P0大审计.md",
    "discussions/Mimir-P0执行审计.md",
    "discussions/Mimir-P0执行总结.md",
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
    json.dump(results, open("/tmp/p1_3_34_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(r["action"] for r in results)
    print("\n统计:", dict(c))
    print("DONE")


if __name__ == "__main__":
    main()
