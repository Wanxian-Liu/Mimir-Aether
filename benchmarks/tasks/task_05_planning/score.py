#!/usr/bin/env python3
"""Task 5 评分: 规划深度"""
import sys, os, json

WORKDIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/benchmark-sandbox"
PLAN = os.path.join(WORKDIR, "planning")

details = []
evidence = {}
score = 0.0
MAX = 20.0

# ===== 阶段1: 审计 =====
audit_file = os.path.join(PLAN, "audit.json")
if os.path.exists(audit_file):
    try:
        with open(audit_file) as f:
            audit = json.load(f)
        has_count = "file_count" in audit or "files" in audit or "count" in audit
        has_words = "word_count" in audit or "words" in audit or "total_words" in audit
        if has_count and has_words:
            score += 5
            details.append("✅ 阶段1: audit.json 有文件数+字数统计")
        elif has_count or has_words:
            score += 3
            details.append("⚠️ 阶段1: audit.json 存在但统计不完整")
        else:
            score += 2
            details.append("⚠️ 阶段1: audit.json 存在但无统计字段")
        evidence["audit"] = audit
    except json.JSONDecodeError:
        score += 1
        details.append("❌ 阶段1: audit.json JSON 无效")
else:
    details.append("❌ 阶段1: audit.json 不存在")

# ===== 阶段2: Frontmatter 转换 =====
output_dir = os.path.join(PLAN, "output")
if os.path.isdir(output_dir):
    output_files = [f for f in os.listdir(output_dir) if f.endswith('.md')]
    if len(output_files) >= 3:
        # 检查 TOML frontmatter
        all_toml = True
        for fname in output_files:
            fpath = os.path.join(output_dir, fname)
            with open(fpath) as f:
                first_line = f.readline().strip()
                if first_line != '+++':
                    all_toml = False
                    evidence[f"frontmatter_{fname}"] = first_line
        if all_toml:
            score += 5
            details.append(f"✅ 阶段2: {len(output_files)} 篇输出，全部 TOML frontmatter")
        else:
            score += 3
            details.append(f"⚠️ 阶段2: 有 {len(output_files)} 篇输出，但部分非 TOML")
    elif len(output_files) > 0:
        score += 2
        details.append(f"⚠️ 阶段2: 仅 {len(output_files)} 篇输出 (需要 3)")
    else:
        details.append("❌ 阶段2: output/ 无 markdown 文件")
    evidence["output_files"] = output_files
else:
    details.append("❌ 阶段2: output/ 目录不存在")

# ===== 阶段3: 交叉引用更新 =====
# 检查 output/ 中的文件是否包含 {{< ref ... >}}
if os.path.isdir(output_dir):
    ref_found = 0
    remaining_old = 0
    for fname in os.listdir(output_dir):
        if not fname.endswith('.md'):
            continue
        fpath = os.path.join(output_dir, fname)
        with open(fpath) as f:
            content = f.read()
        if '{{<' in content and 'ref' in content:
            ref_found += 1
        if 'docs/' in content and '.md' in content:
            remaining_old += 1
    if ref_found >= 1 and remaining_old == 0:
        score += 5
        details.append(f"✅ 阶段3: {ref_found} 个 ref 链接，无旧格式残留")
    elif ref_found >= 1:
        score += 3
        details.append(f"⚠️ 阶段3: 有 ref 链接但仍有 {remaining_old} 个旧格式")
    else:
        details.append(f"❌ 阶段3: 无 ref 链接，{remaining_old} 个旧格式残留")
    evidence["ref_count"] = ref_found
    evidence["old_links"] = remaining_old

# ===== 阶段4: 验证 =====
# 检查 output/ 中无 YAML frontmatter (以 --- 开头)
if os.path.isdir(output_dir):
    yaml_remains = 0
    for fname in os.listdir(output_dir):
        if not fname.endswith('.md'):
            continue
        fpath = os.path.join(output_dir, fname)
        with open(fpath) as f:
            first_line = f.readline().strip()
            if first_line == '---':
                yaml_remains += 1
    if yaml_remains == 0:
        score += 5
        details.append("✅ 阶段4: 无残留 YAML frontmatter")
    else:
        details.append(f"❌ 阶段4: {yaml_remains} 个文件仍有 YAML frontmatter")
    evidence["yaml_remains"] = yaml_remains

result = {"score": score, "max": MAX, "details": details, "evidence": evidence}
print(json.dumps(result, ensure_ascii=False))
