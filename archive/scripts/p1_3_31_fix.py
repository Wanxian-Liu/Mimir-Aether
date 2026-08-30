#!/usr/bin/env python3
"""P1-3.1 第一批 15 张卡 source 补齐 — 确定性规则并行版（3 进程 × 5 卡）。

用户规则（2026-08-12）：
- 真溯源（卡内 URL/arXiv/真实本地路径/wikilink，test -f 验证）或诚实 unknown
- 禁止 "待补raw" 占位
- 只改 frontmatter 的 source/sources 字段，不动正文与其他字段

用法: python3 scripts/p1_3_31_fix.py <batch_index 0|1|2>
"""
import os, re, sys, json

WIKI = "/home/rayliu/wiki"
URL_RE = re.compile(r"https?://[^\s\)\]\}>\"'`，。、；：|]+")
ARXIV_RE = re.compile(r"arXiv\s*:\s*([\d.]+)", re.I)
ARXIV_URL_RE = re.compile(r"https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/([\d.]+)")
LOCAL_RE = re.compile(r"(?:readings/books/[^\s\)\]\}>\"'`，。、；：|]+\.md|raw/[^\s\)\]\}>\"'`，。、；：|]+\.(?:md|pdf|txt|json))")
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
BAD_URL_HINTS = ("127.0.0.1", "localhost", "rsproxy", "example.com")

BATCHES = [
    [
        "concepts/18bug修复执行记录.md",
        "concepts/1c-policy.md",
        "concepts/2026-08-11-整理方案-完整版.md",
        "concepts/A1修复-截断与后置审计-20260805.md",
        "concepts/AGENTS执行纪律审计-20260809.md",
    ],
    [
        "concepts/AgencyAgent更新记录-20260805.md",
        "concepts/AgencyAgent角色使用规则-20260805.md",
        "concepts/Buzz四方cron配置-20260804.md",
        "concepts/Buzz接入进展报告-20260803.md",
        "concepts/Hermes-SOUL审计更新-20260805.md",
    ],
    [
        "concepts/Loki审计模板-v2-9步执行清单.md",
        "concepts/Loki结构健康度自盯指标.md",
        "concepts/Mimir-P0工程记录-收益评估.md",
        "concepts/Mimir-P1-1-source规范报告.md",
        "concepts/Mimir-P1-2-source统一报告.md",
    ],
]


def path_exists(p):
    p2 = os.path.expanduser(p)
    if p2.startswith("/"):
        return os.path.exists(p2)
    return os.path.exists(os.path.join(WIKI, p2))


def clean_url(u):
    u = u.rstrip(".,;:)]}>`*，。、；：）】」』") or u
    u = re.sub(r"[）→」】].*$", "", u)
    if any(h in u for h in BAD_URL_HINTS):
        return None
    if re.search(r"[\u4e00-\u9fff]", u):
        return None
    if "`" in u or " " in u:
        return None
    return u


def get_field(fm, field):
    lines = fm.splitlines()
    idxs = [i for i, l in enumerate(lines) if re.match(rf"^{field}\s*:", l)]
    if not idxs:
        return None
    idx = idxs[0]
    first = lines[idx].split(":", 1)[1].strip()
    vals = []
    if first.startswith("["):
        inner = first[1:-1]
        vals = [x.strip().strip('"').strip("'") for x in inner.split(",")] if inner.strip() else []
    elif first:
        vals = [first.strip('"').strip("'")]
    for l in lines[idx + 1:]:
        if re.match(r"^[a-z_]+:", l):
            break
        if l.strip().startswith("- "):
            vals.append(l.strip()[2:].strip().strip('"').strip("'"))
        elif l.strip():
            vals.append(l.strip().strip('"').strip("'"))
    return [v for v in vals if v]


def find_candidates(rel, text, fm):
    cands = []
    url = get_field(fm, "url")
    if url:
        for u in url:
            c = clean_url(u)
            if c and c not in cands:
                cands.append(c)
    body = text
    for m in ARXIV_URL_RE.finditer(body):
        c = f"https://arxiv.org/abs/{m.group(1)}"
        if c not in cands:
            cands.append(c)
    for m in ARXIV_RE.finditer(body):
        c = f"https://arxiv.org/abs/{m.group(1)}"
        if c not in cands:
            cands.append(c)
    for u in URL_RE.findall(body):
        c = clean_url(u)
        if c and c not in cands:
            cands.append(c)
    for p in LOCAL_RE.findall(body):
        p = p.rstrip(".,;:])}`") or p
        if p not in cands and path_exists(p):
            cands.append(p)
    for m in LINK_RE.finditer(text):
        tgt = m.group(1).strip().replace("\\", "/")
        base = rel.split("/")[-1].replace(".md", "")
        if tgt.replace(".md", "") == base or tgt == rel.replace(".md", ""):
            continue
        for prefix in ("discussions/", "concepts/", "entities/", "comparisons/"):
            cand = prefix + tgt
            if not cand.endswith(".md"):
                cand += ".md"
            if cand not in cands and path_exists(cand) and cand != rel:
                cands.append(cand)
        cand = tgt + (".md" if not tgt.endswith(".md") else "")
        if cand not in cands and path_exists(cand) and cand != rel:
            cands.append(cand)
    return cands[:4]


def fix_file(rel):
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

    pl_idx = [i for i, l in enumerate(fm_lines) if re.match(r"^sources\s*:", l)]
    s_idx = [i for i, l in enumerate(fm_lines) if re.match(r"^source\s*:", l)]
    action = None
    new_vals = None
    src_line_idx = None

    cands = find_candidates(rel, text, fm)

    if pl_idx:
        # 复数 sources -> 单数 source，值校验
        src_line_idx = pl_idx[0]
        vals = get_field(fm, "sources") or []
        valid = [v for v in vals if v.startswith("http") or path_exists(v)]
        if valid:
            new_vals = valid
            action = "renamed"
        elif cands:
            new_vals = cands
            action = "renamed"
        else:
            new_vals = ["unknown"]
            action = "renamed"
    elif s_idx:
        src_line_idx = s_idx[0]
        vals = get_field(fm, "source") or []
        cur = vals[0] if vals else ""
        if cur == "待补raw" or cur == "unknown（待溯源）" or cur == "unknown":
            if cands:
                new_vals = cands
                action = "fixed"
            else:
                new_vals = ["unknown"]
                action = "unknown"
        elif cur.startswith("http") or path_exists(cur):
            # 已合法，不动（但可能有多行重复 source，需要去重）
            action = "keep"
        else:
            # 非法值（机构名、docs/ 开头等）
            if cands:
                new_vals = cands
                action = "fixed"
            else:
                new_vals = ["unknown"]
                action = "unknown"
    else:
        # 无 source 字段
        src_line_idx = None
        if cands:
            new_vals = cands
            action = "added"
        else:
            new_vals = ["unknown"]
            action = "added"

    if action in ("keep", "no-frontmatter"):
        return {"file": rel, "action": action, "source": None}

    # 重建 frontmatter：删除所有 source/sources 行（含多行列表值），在 url 字段后插入新 source
    new_fm = []
    i = 0
    inserted = False
    while i < len(fm_lines):
        line = fm_lines[i]
        if re.match(r"^sources?\s*:", line):
            # 跳过该字段及其列表续行
            i += 1
            while i < len(fm_lines) and (fm_lines[i].startswith("  - ") or (fm_lines[i].startswith(" ") and not re.match(r"^[a-z_]+:", fm_lines[i]))):
                i += 1
            continue
        new_fm.append(line)
        # 在 url 字段后插入 source（如果没有 url 字段，则插在文件末尾字段前——简化：直接追加在最后一个字段后）
        i += 1
    # 插入 source（保持 YAML 缩进一致）
    if new_vals and len(new_vals) == 1:
        new_fm.append(f'source: "{new_vals[0]}"')
    elif new_vals:
        new_fm.append("source:")
        for v in new_vals:
            new_fm.append(f'  - "{v}"')
    else:
        new_fm.append('source: "unknown"')

    new_text = "---\n" + "\n".join(new_fm) + "\n---\n" + "\n".join(lines[end + 1:])
    open(path, "w", encoding="utf-8").write(new_text)

    # 验证
    verify = open(path, encoding="utf-8").read()
    ok = False
    if "source:" in verify.split("---")[1] if verify.startswith("---") else False:
        ok = True
    return {"file": rel, "action": action, "source": new_vals, "verified": ok}


def main():
    batch_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    results = []
    for rel in BATCHES[batch_idx]:
        r = fix_file(rel)
        results.append(r)
        print(f"{r['file']} | {r['action']} | {r.get('source')} | verified={r.get('verified')}")
    json.dump(results, open(f"/tmp/p1_3_31_batch{batch_idx}_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("DONE")


if __name__ == "__main__":
    main()
