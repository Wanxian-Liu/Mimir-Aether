#!/usr/bin/env python3
"""P1-3 source 增强修复脚本 v2（确定性规则，不编造）。

规则（每张 concepts/discussions/comparisons 卡）:
  1. 复数 sources: -> 单数 source:（值逐项校验，坏项删除）
  2. source 非法(fake)/缺/空/待补raw -> 候选来源按优先级:
     a. frontmatter url: 字段值
     b. 正文 arXiv 编号 -> https://arxiv.org/abs/<id>
     c. 正文 http URL（过滤垃圾/本地地址）
     d. 正文 readings/ raw/ 真实文件路径（test -f）
     e. 正文 [[wikilink]] 指向的 discussions//concepts/ 卡（test -f 且非自身）
     f. 都没有 -> source: "待补raw"
  3. 只改 frontmatter 的 source/sources 行，不动正文与其他字段
  4. 写后验证: source 落盘 + 本地路径存在

用法: python3 scripts/p1_3_fix2.py
"""
import os, re, sys, json, glob

WIKI = "/home/rayliu/wiki"
URL_RE = re.compile(r"https?://[^\s\)\]\}>\"'`，。、；：|]+")
ARXIV_RE = re.compile(r"arXiv\s*:\s*([\d.]+)", re.I)
ARXIV_URL_RE = re.compile(r"https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/([\d.]+)")
LOCAL_RE = re.compile(r"(?:readings/books/[^\s\)\]\}>\"'`，。、；：|]+\.md|raw/[^\s\)\]\}>\"'`，。、；：|]+\.(?:md|pdf|txt|json))")
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
BAD_URL_HINTS = ("127.0.0.1", "localhost", "rsproxy", "example.com")


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
    """返回候选 source 列表（已去重、已验证本地路径）。"""
    cands = []

    # a. frontmatter url 字段
    url = get_field(fm, "url")
    if url:
        for u in url:
            c = clean_url(u)
            if c and c not in cands:
                cands.append(c)

    # b. arXiv 编号 -> 构造 URL
    body = text
    for m in ARXIV_URL_RE.finditer(body):
        c = f"https://arxiv.org/abs/{m.group(1)}"
        if c not in cands:
            cands.append(c)
    for m in ARXIV_RE.finditer(body):
        c = f"https://arxiv.org/abs/{m.group(1)}"
        if c not in cands:
            cands.append(c)

    # c. 正文 URL
    for u in URL_RE.findall(body):
        c = clean_url(u)
        if c and c not in cands:
            cands.append(c)

    # d. 本地路径（readings/ raw/）
    for p in LOCAL_RE.findall(body):
        p = p.rstrip(".,;:])}`") or p
        if p not in cands and path_exists(p):
            cands.append(p)

    # e. wikilink -> discussions/ concepts/ entities/ 卡
    for m in LINK_RE.finditer(text):
        tgt = m.group(1).strip()
        tgt = tgt.replace("\\", "/")
        # 跳过指向自身的
        base = rel.split("/")[-1].replace(".md", "")
        if tgt.replace(".md", "") == base or tgt == rel.replace(".md", ""):
            continue
        for prefix in ("discussions/", "concepts/", "entities/", "comparisons/"):
            cand = prefix + tgt
            if not cand.endswith(".md"):
                cand += ".md"
            if cand not in cands and path_exists(cand) and cand != rel:
                cands.append(cand)
        # 纯文件名（不带前缀）
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

    if pl_idx:
        # 复数 -> 单数，值校验
        i = pl_idx[0]
        val = fm_lines[i].split(":", 1)[1].strip()
        items = []
        if val.startswith("["):
            inner = val[1:-1]
            items = [x.strip().strip('"').strip("'") for x in inner.split(",")] if inner.strip() else []
        else:
            items = [val.strip('"').strip("'")]
        valid = [v for v in items if (v.startswith("http") or v == "待补raw" or path_exists(v))]
        if not valid:
            # 全部非法 -> 从正文/url 找
            cands = find_candidates(rel, text, fm)
            if cands:
                valid, action = cands[:3], "renamed-from-bad"
            else:
                valid, action = ["待补raw"], "renamed-to-placeholder"
        else:
            action = "renamed"
        new_vals = valid
        src_line_idx = i
    elif s_idx:
        i = s_idx[0]
        # 用 get_field 正确拆包内联列表
        vals = get_field(fm, "source")
        if not vals or vals == [""]:
            cands = find_candidates(rel, text, fm)
            new_vals = (cands or ["待补raw"])[:3]
            action = "filled-empty" if cands else "placeholder"
            src_line_idx = i
        elif vals[0] == "待补raw":
            cands = find_candidates(rel, text, fm)
            if cands:
                new_vals, action = cands[:3], "replaced-placeholder"
                src_line_idx = i
            else:
                return {"file": rel, "action": "placeholder-kept", "source": None}
        else:
            # 已有单数，校验（vals 来自 get_field 拆包）
            bad = [v for v in vals if v and not v.startswith("http") and not path_exists(v)]
            if bad:
                cands = find_candidates(rel, text, fm)
                new_vals = (cands or ["待补raw"])[:3]
                action = "fixed-fake" if cands else "fake-to-placeholder"
                src_line_idx = i
            else:
                return {"file": rel, "action": "ok", "source": None}
    else:
        # 完全缺 source
        cands = find_candidates(rel, text, fm)
        new_vals = (cands or ["待补raw"])[:3]
        action = "added" if cands else "placeholder"
        # 插入位置: tags 后
        insert_at = None
        for i, l in enumerate(fm_lines):
            if re.match(r"^tags\s*:", l):
                insert_at = i + 1
                break
        if insert_at is None:
            insert_at = len(fm_lines)
        if len(new_vals) == 1:
            line = 'source: "' + new_vals[0] + '"'
        else:
            line = "source:\n" + "\n".join('  - "' + v + '"' for v in new_vals)
        fm_lines.insert(insert_at, line)

    # 应用修改（替换源行）
    if src_line_idx is not None and action not in ("ok",):
        if len(new_vals) == 1:
            fm_lines[src_line_idx] = 'source: "' + new_vals[0] + '"'
        else:
            fm_lines[src_line_idx] = "source:\n" + "\n".join('  - "' + v + '"' for v in new_vals)

    new_text = "---\n" + "\n".join(fm_lines) + "\n---\n" + body
    open(path, "w", encoding="utf-8").write(new_text)

    # 验证
    verify = open(path, encoding="utf-8").read()
    if re.search(r"^source\s*:", verify, re.M) is None:
        return {"file": rel, "action": "VERIFY-FAIL", "source": new_vals}
    for v in new_vals:
        if not v.startswith("http") and v != "待补raw" and not path_exists(v):
            return {"file": rel, "action": "VERIFY-FAIL", "source": new_vals}
    return {"file": rel, "action": action, "source": new_vals}


def main():
    include_entities = "--entities" in sys.argv
    files = []
    dirs = ("concepts", "discussions", "comparisons") + (("entities",) if include_entities else ())
    for d in dirs:
        for f in sorted(glob.glob(f"{WIKI}/{d}/*.md")):
            if not os.path.basename(f).startswith("_"):
                files.append(f"{d}/{os.path.basename(f)}")

    results = []
    for rel in files:
        r = fix_file(rel)
        results.append(r)

    from collections import Counter
    counter = Counter(r["action"] for r in results)
    print("动作分布:", dict(counter))
    for r in results:
        if r["action"] not in ("ok", "placeholder-kept"):
            print(f"  {r['action']:24s} {r['file']} -> {r['source']}")
    json.dump(results, open("/tmp/p1_3_fix2_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
