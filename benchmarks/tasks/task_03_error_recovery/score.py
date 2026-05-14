#!/usr/bin/env python3
"""Task 3 评分: 错误恢复"""
import sys, os, json, stat

WORKDIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/benchmark-sandbox"
ERR = os.path.join(WORKDIR, "errrec")

details = []
evidence = {}
score = 0.0
MAX = 15.0

# ===== A: 损坏 JSON (5分) =====
broken = os.path.join(ERR, "broken.json")
if os.path.exists(broken):
    try:
        with open(broken) as f:
            json.load(f)
        # JSON 现在是有效的 → 说明 Agent 检测并修复了
        score += 5
        details.append("✅ A: broken.json 已被修复为有效 JSON")
        evidence["broken_fixed"] = True
    except json.JSONDecodeError:
        # JSON 仍然损坏 → Agent 可能崩溃或没处理
        details.append("❌ A: broken.json 仍然无效 (Agent 未处理)")
        evidence["broken_fixed"] = False
    except Exception as e:
        details.append(f"⚠️ A: broken.json 检查异常: {e}")
else:
    # 文件不见了 → 可能是 Agent 删除并重建了
    details.append("⚠️ A: broken.json 不存在 (可能被删除)")

# ===== B: 只读文件 (5分) =====
readonly = os.path.join(ERR, "readonly.txt")
original_content = "original content - do not overwrite"
score_b = 0

# 检查 1: 原文件内容是否被保护 (2分)
if os.path.exists(readonly):
    with open(readonly) as f:
        current = f.read()
    if current.strip() == original_content.strip():
        score_b += 2
        details.append("✅ B: readonly.txt 原始内容未被破坏")
        evidence["readonly_preserved"] = True
    else:
        details.append("⚠️ B: readonly.txt 内容已被修改")
        evidence["readonly_preserved"] = False
else:
    score_b += 1
    details.append("⚠️ B: readonly.txt 不存在")

# 检查 2: Agent 是否创建了替代文件 (如 readonly_new.txt) (2分)
alt_files = [f for f in os.listdir(ERR) if 'readonly' in f.lower() and f != 'readonly.txt']
if alt_files:
    score_b += 2
    details.append(f"✅ B: Agent 创建了替代文件: {alt_files}")

# 检查 3: 权限是否被正确处理 (1分)
try:
    if os.path.exists(readonly):
        perms = stat.S_IMODE(os.stat(readonly).st_mode)
        if perms == 0o444:
            score_b += 0  # 保持原样
            evidence["readonly_perms"] = "preserved 444"
        elif perms & 0o200:  # 可写了
            score_b += 1
            details.append("✅ B: 正确处理了只读权限 (chmod 后写入)")
            evidence["readonly_perms"] = "fixed"
except:
    pass

score += score_b
if score_b < 3:
    details.append(f"❌ B: 只读文件处理不足 ({score_b}/5)")

# ===== C: 目录当文件 (5分) =====
data_dir = os.path.join(ERR, "data_dir")
score_c = 0

# 检查 1: data_dir 还是目录吗？
if os.path.isdir(data_dir):
    # 列出目录内容 → Agent 是否做了什么？
    contents = os.listdir(data_dir)
    # 如果 Agent 创建了 data_dir.json 在上级目录
    parent_json = os.path.join(ERR, "data_dir.json")
    if os.path.exists(parent_json):
        score_c += 5
        details.append("✅ C: 检测到目录/文件混淆，创建了 data_dir.json")
    elif len(contents) > 1:
        score_c += 3
        details.append(f"⚠️ C: 目录仍存在但内容有变化 ({len(contents)} 项)")
    else:
        score_c += 1
        details.append("❌ C: 目录未变化，Agent 似乎未处理此错误")
    evidence["data_dir_contents"] = contents
elif os.path.isfile(data_dir):
    score_c += 3
    details.append("⚠️ C: data_dir 变成了文件 (可能被覆盖)")
    evidence["data_dir_type"] = "file"
else:
    details.append("❌ C: data_dir 不存在")
    evidence["data_dir_type"] = "missing"

score += score_c

result = {"score": score, "max": MAX, "details": details, "evidence": evidence}
print(json.dumps(result, ensure_ascii=False))
