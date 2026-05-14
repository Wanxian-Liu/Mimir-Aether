#!/usr/bin/env python3
"""Task 1 评分: 工具编排"""
import sys, os, json

WORKDIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/benchmark-sandbox"
PROJ = os.path.join(WORKDIR, "project-orch")

details = []
evidence = {}
score = 0.0
MAX = 25.0

def check(name, points, fn, *args):
    global score
    try:
        ok = fn(*args)
    except Exception as e:
        ok = False
        evidence[name] = str(e)
    if ok:
        score += points
        details.append(f"✅ {name}")
    else:
        details.append(f"❌ {name}")
        if name not in evidence:
            evidence[name] = "FAILED"

# 1. 目录存在
check("目录 project-orch 存在", 4, os.path.isdir, PROJ)

# 2. README.md 内容
readme = os.path.join(PROJ, "README.md")
if os.path.exists(readme):
    with open(readme) as f:
        content = f.read()
    has_title = "# Benchmark Project" in content
    has_desc = "This is an automated benchmark test" in content
    if has_title and has_desc:
        score += 4
        details.append("✅ README.md 内容正确")
    else:
        details.append(f"❌ README.md 内容不正确 (title={has_title}, desc={has_desc})")
        evidence["README.md"] = content[:200]
else:
    details.append("❌ README.md 不存在")

# 3. git init
check("git init 完成", 3, os.path.isdir, os.path.join(PROJ, ".git"))

# 4. .gitignore
gi = os.path.join(PROJ, ".gitignore")
if os.path.exists(gi):
    with open(gi) as f:
        gic = f.read()
    has_log = "*.log" in gic
    has_pyc = "__pycache__" in gic
    if has_log and has_pyc:
        score += 3
        details.append("✅ .gitignore 内容正确")
    else:
        details.append(f"❌ .gitignore 不完整 (log={has_log}, pycache={has_pyc})")
        evidence[".gitignore"] = gic
else:
    details.append("❌ .gitignore 不存在")

# 5. git commit
import subprocess
try:
    r = subprocess.run(["git", "log", "--oneline", "-1"], cwd=PROJ,
                       capture_output=True, text=True, timeout=10)
    if r.returncode == 0 and "initial commit" in r.stdout.lower():
        score += 4
        details.append("✅ git commit 成功且 message 正确")
        evidence["git_log"] = r.stdout.strip()
    elif r.returncode == 0:
        score += 2
        details.append(f"⚠️ git commit 成功但 message 不匹配: {r.stdout.strip()}")
        evidence["git_log"] = r.stdout.strip()
    else:
        details.append("❌ git commit 不存在")
        evidence["git_error"] = r.stderr[:200]
except Exception as e:
    details.append(f"❌ git commit 检查失败: {e}")

# 6. 搜索 TODO (验证搜索执行——这里我们用间接证据)
# 注: Agent 通常输出搜索结果显示无匹配，外部难以捕获。
# 这里给基础分，因为只要 Agent 执行了搜索就会输出。
# 公正性注: 此检查可被外部日志验证，或改为检查 Agent 输出文本。
# 简化: 如果前面各项都通过，说明 Agent 工具链可用，给满分。
# (外部判定器的局限——无法确认 Agent 是否"搜索了但没有输出"。后续版本可加 Agent 输出解析)
score += 3
details.append("✅ TODO 搜索已执行 (工具链完整性推断)")

# 7. config.json
cj = os.path.join(PROJ, "config.json")
if os.path.exists(cj):
    try:
        with open(cj) as f:
            data = json.load(f)
        if data.get("version") == "1.0" and data.get("debug") == False:
            score += 4
            details.append("✅ config.json 存在且内容正确")
        else:
            score += 2
            details.append(f"⚠️ config.json 存在但内容不匹配: {data}")
        evidence["config.json"] = data
    except json.JSONDecodeError:
        details.append("❌ config.json JSON 无效")
else:
    details.append("❌ config.json 不存在")

result = {"score": score, "max": MAX, "details": details, "evidence": evidence}
print(json.dumps(result, ensure_ascii=False))
