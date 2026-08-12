#!/usr/bin/env python3
"""P1-3.3 source 补齐 — 确定性脚本（复用 p1_3_31_fix.fix_file + p1_3_32_pass2 规则）。

批次：concepts 占位存量 45 张（用户口径 40 张，scan 精确口径）+ discussions 前 15 张。
规则（用户 2026-08-12，同 P1-3.2）：
- 真溯源（卡内 URL/arXiv/真实本地路径/wikilink/related/markdown链接，test -f 验证）或诚实 unknown
- 禁止 "待补raw" / "unknown（待溯源）" 占位
- 只改 frontmatter 的 source/sources 字段，不动正文与其他字段
- 每张处理后立即 read back 验证

用法: python3 scripts/p1_3_33_fix.py
"""
import importlib.util, json, os, re

WIKI = "/home/rayliu/wiki"

# 加载 p1_3_31_fix 复用 fix_file / find_candidates
spec = importlib.util.spec_from_file_location(
    "p1_3_31_fix", "/home/rayliu/src/MimirAether/scripts/p1_3_31_fix.py")
p131 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p131)
fix_file = p131.fix_file

# 目标卡：concepts 45（scan 精确口径）+ discussions 前 15（mtime 旧->新）
CARDS = [
    # --- concepts 占位存量 45 张 ---
    "concepts/Mimir-P1-3-source补齐报告.md",
    "concepts/evolution-knowledge-base.md",
    "concepts/graphrag-paper.md",
    "concepts/graphrag-survey.md",
    "concepts/guard接错循环-修复失效根因-20260805.md",
    "concepts/harness-engineering.md",
    "concepts/hermes-cron-scheduling-learning.md",
    "concepts/hermes-curator-usage-analysis.md",
    "concepts/hermes-moa-memory-lsp-learning.md",
    "concepts/hipporag.md",
    "concepts/hipporag2.md",
    "concepts/lazygraphrag.md",
    "concepts/lightrag.md",
    "concepts/memory-awakening-three-layer-architecture.md",
    "concepts/mimir-auto-load-standardization.md",
    "concepts/mimir-ghost-skill-cleaning.md",
    "concepts/philosophy-engineering-evo-mapping.md",
    "concepts/quantum-plus-ai-quantum-ai.md",
    "concepts/rag-survey-gao.md",
    "concepts/schema升级评估-BRAN-OKF.md",
    "concepts/smart-manufacturing-aiot-knowledge-system.md",
    "concepts/task_state验证-20260805.md",
    "concepts/worldweaver-loom-system-architecture.md",
    "concepts/三Agent体检审计-20260805.md",
    "concepts/不落盘根因调查-20260805.md",
    "concepts/临时解决记录-四方互等回执停滞-20260805.md",
    "concepts/以落盘为主-去掉附件-20260805.md",
    "concepts/同角色调整规则-20260805.md",
    "concepts/四方完成信号机制.md",
    "concepts/四方成长方案-原子任务PiAgent角色.md",
    "concepts/四方评分器-可执行版v1.md",
    "concepts/四方评分器v3-Anthropic式.md",
    "concepts/四方评分器v4-Harness通用维度.md",
    "concepts/四方评分器框架-草案.md",
    "concepts/工程系统知识网-枢纽卡.md",
    "concepts/提示词工程能力升级-20260804.md",
    "concepts/收件箱残留问题修复-20260804.md",
    "concepts/智能制造名词词典-销售认知版.md",
    "concepts/硬盘整理P0P1执行-20260805.md",
    "concepts/织界团队理念-刘哥愿景.md",
    "concepts/观察理念-织鉴前身.md",
    "concepts/观察记录-试用落盘行为-20260805.md",
    "concepts/角色使用统计.md",
    "concepts/语义搜索知识网-枢纽卡.md",
    "concepts/身份区分协议-Hermes琬弦与OpenClaw琬弦.md",
    # --- discussions 新 15 张（mtime 旧->新）---
    "discussions/12项诊断-#5-#10-OpenClaw妹-执行报告-2026-07-27.md",
    "discussions/18bug修复执行-四方会诊.md",
    "discussions/18bug第二轮-Buzz四方讨论记录.md",
    "discussions/2026-07-31-Loki根因调查-体检报告.md",
    "discussions/2026-08-11-今日总收束.md",
    "discussions/2026-08-11-最终总结报告.md",
    "discussions/2026-08-12-Mimir-P1-2-source统一-@hermes信号.md",
    "discussions/2026-08-12-Mimir-P1-3-source补齐-@hermes信号.md",
    "discussions/300088四方角色研究-第一次实战.md",
    "discussions/300088实战复盘-四方反思.md",
    "discussions/316角色分配模式-四方讨论.md",
    "discussions/Agency Agent体系-待办2下沉角色.md",
    "discussions/Agency Agent体系落地-四方讨论总卡.md",
    "discussions/Agency Agent角色分配-四方认领.md",
    "discussions/B组复盘-删改审慎-四方再讨论.md",
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
    json.dump(results, open("/tmp/p1_3_33_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(r["action"] for r in results)
    print("\n统计:", dict(c))
    print("DONE")


if __name__ == "__main__":
    main()
