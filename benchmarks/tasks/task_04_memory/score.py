#!/usr/bin/env python3
"""Task 4 评分: 记忆持久"""
import sys, os, json

WORKDIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/benchmark-sandbox"
MEM = os.path.join(WORKDIR, "memory")

details = []
evidence = {}
score = 0.0
MAX = 15.0

memfile = os.path.join(MEM, "session_memory.json")

# 1. 文件存在且 JSON 有效
if os.path.exists(memfile):
    try:
        with open(memfile) as f:
            data = json.load(f)
        score += 3
        details.append("✅ session_memory.json 存在且 JSON 有效")
        evidence["file_exists"] = True
    except (json.JSONDecodeError, IOError) as e:
        details.append(f"❌ session_memory.json 无效: {e}")
        evidence["parse_error"] = str(e)
        print(json.dumps({"score": score, "max": MAX, "details": details, "evidence": evidence}, ensure_ascii=False))
        sys.exit(0)
else:
    details.append("❌ session_memory.json 不存在")
    evidence["file_exists"] = False
    print(json.dumps({"score": score, "max": MAX, "details": details, "evidence": evidence}, ensure_ascii=False))
    sys.exit(0)

# 2. project_name
if data.get("project_name") == "AetherFlow":
    score += 4
    details.append("✅ project_name == AetherFlow")
else:
    details.append(f"❌ project_name 错误: {data.get('project_name')}")
evidence["project_name"] = data.get("project_name")

# 3. port
port = data.get("port")
if port == 9090 or str(port) == "9090":
    score += 4
    details.append("✅ port == 9090")
else:
    details.append(f"❌ port 错误: {port}")
evidence["port"] = port

# 4. database
if data.get("database") == "PostgreSQL":
    score += 4
    details.append("✅ database == PostgreSQL")
else:
    details.append(f"❌ database 错误: {data.get('database')}")
evidence["database"] = data.get("database")

# bonus: 检查 timestamp
if "created_at" in data:
    details.append("✅ created_at 字段存在")
evidence["created_at"] = data.get("created_at")

result = {"score": score, "max": MAX, "details": details, "evidence": evidence}
print(json.dumps(result, ensure_ascii=False))
