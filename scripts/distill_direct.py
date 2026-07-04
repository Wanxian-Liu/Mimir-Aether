#!/usr/bin/env python3
"""蒸馏直接调用 — 从 provider_registry 获取 key 然后调 DeepSeek"""
import json, os, sys, time
from datetime import datetime, timezone

import yaml

PERSISTENT_PATH = os.path.expanduser("~/.mimiraether/data/persistent.json")

# 1. Get API key from config.yaml (Gateway 真源)
config_path = os.path.expanduser("~/.mimiraether/config.yaml")
with open(config_path) as f:
    cfg = yaml.safe_load(f)
api_key = cfg.get("providers", {}).get("deepseek", {}).get("api_key", "")
source = "config.yaml"
print(f"[OK] key from {source}, len={len(api_key)}, prefix={api_key[:7] if api_key else 'N/A'}")

if not api_key or len(api_key) < 30:
    # Fallback: try os.environ
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    print(f"[WARN] fallback to os.environ, len={len(api_key)}")

if not api_key or api_key == "***" or len(api_key) < 30:
    print("[FAIL] no valid key")
    sys.exit(1)

# 2. Read persistent.json
with open(PERSISTENT_PATH) as f:
    data = json.load(f)

mem = data.get("memory", {})
kd_list = mem.get("key_decisions", [])
lp_list = mem.get("learned_patterns", [])
bc_list = mem.get("behavioral_constraints", [])

print(f"  key_decisions: {len(kd_list)}")
print(f"  learned_patterns: {len(lp_list)}")
print(f"  behavioral_constraints: {len(bc_list)}")

# 3. Build prompt
memory_text = (
    f"=== key_decisions ({len(kd_list)} 条) ===" +
    "".join(f"\n- {json.dumps(k, ensure_ascii=False)}" for k in kd_list) +
    f"\n\n=== learned_patterns ({len(lp_list)} 条) ===" +
    "".join(f"\n- {json.dumps(p, ensure_ascii=False)}" for p in lp_list) +
    f"\n\n=== behavioral_constraints ({len(bc_list)} 条) ===" +
    "".join(f"\n- {json.dumps(b, ensure_ascii=False)}" for b in bc_list)
)

DISTILL_PROMPT_TEMPLATE = """你是一个梦境记忆蒸馏系统。你的任务是将输入的大量决策和模式记忆去重、合并、精炼。
规则：
1. **key_decisions** 压缩到最多 20 条——合并相关决策，去掉过时或重复的。
2. **learned_patterns** 压缩到最多 30 条——合并同类模式，去掉不再适用的。
3. **behavioral_constraints** 保留最多 5 条最关键的、最具约束力的行为规则。
4. 保留最重要、最独特的条目——质量优先于数量。
5. 为每条决策和模式添加 **tip_type** 字段，分类为 "strategy"（策略类）、"recovery"（恢复类）、"optimization"（优化类）。
6. 为每条决策添加 **cause_chain** 字段：{{"direct": "直接触发原因", "proximate": "近因/中间原因", "root": "根因/系统性问题"}}。
7. 每条约束格式：{{"rule": "...", "source": "distilled", "evidence": "..."}}
8. **self_contradiction** 为单条字符串——分析最严重的自我矛盾。
9. 只输出 JSON，不要解释过程。

输入记忆：
{memory_text}

输出格式：
{{"key_decisions": [{{"decision": "...", "context": "...", "tip_type": "strategy|recovery|optimization", "cause_chain": {{"direct": "...", "proximate": "...", "root": "..."}}}}], "learned_patterns": [{{"pattern": "...", "evidence": "...", "tip_type": "strategy|recovery|optimization"}}], "behavioral_constraints": [{{"rule": "...", "source": "distilled", "evidence": "..."}}], "self_contradiction": "..."}}"""

prompt = DISTILL_PROMPT_TEMPLATE.format(memory_text=memory_text)
print(f"[OK] prompt: {len(prompt)} 字符")

# 4. Call DeepSeek API directly
import urllib.request
payload = json.dumps({
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 4096,
    "temperature": 0.3,
}).encode("utf-8")

req = urllib.request.Request(
    "https://api.deepseek.com/v1/chat/completions",
    data=payload,
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
)

print("[..] 调用 API...")
start = time.time()
with urllib.request.urlopen(req, timeout=120) as resp:
    body = json.loads(resp.read().decode("utf-8"))
elapsed = time.time() - start
print(f"[OK] API 耗时: {elapsed:.1f}s")

content = body["choices"][0]["message"]["content"].strip()
if content.startswith("```"):
    content = content.split("\n", 1)[-1]
    content = content.rsplit("```", 1)[0].strip()

result = json.loads(content)
print(f"[OK] 解析成功")
print(f"  key_decisions: {len(result.get('key_decisions', []))}")
print(f"  learned_patterns: {len(result.get('learned_patterns', []))}")
print(f"  behavioral_constraints: {len(result.get('behavioral_constraints', []))}")
print(f"  self_contradiction: {'有' if result.get('self_contradiction', '').strip() else '无'}")

# Stats
kd_new = result.get("key_decisions", [])
lp_new = result.get("learned_patterns", [])
tipped_kd = sum(1 for k in kd_new if k.get("tip_type"))
chained_kd = sum(1 for k in kd_new if k.get("cause_chain"))
tipped_lp = sum(1 for p in lp_new if p.get("tip_type"))
print(f"  tip_type(kd): {tipped_kd}/{len(kd_new)}")
print(f"  cause_chain: {chained_kd}/{len(kd_new)}")
print(f"  tip_type(lp): {tipped_lp}/{len(lp_new)}")

# 5. Write back
mem = data.setdefault("memory", {})
old_decisions = len(mem.get("key_decisions", []))
old_patterns = len(mem.get("learned_patterns", []))
old_constraints = len(mem.get("behavioral_constraints", []))

_MAX_DECISIONS = 20
_MAX_PATTERNS = 30
_MAX_CONSTRAINTS = 5
mem["key_decisions"] = kd_new[:_MAX_DECISIONS]
mem["learned_patterns"] = lp_new[:_MAX_PATTERNS]
if len(result.get("behavioral_constraints", [])) > 0:
    mem["behavioral_constraints"] = result["behavioral_constraints"][:_MAX_CONSTRAINTS]

# Write contradiction report
contradiction = result.get("self_contradiction", "")
if contradiction and contradiction.strip():
    cpath = os.path.expanduser("~/.mimiraether/data/self_contradiction_report.json")
    existing = []
    if os.path.isfile(cpath):
        with open(cpath) as f:
            existing = json.load(f) or []
    existing.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contradiction": contradiction.strip(),
    })
    existing = existing[-10:]
    with open(cpath, "w") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"[OK] contradiction report written ({len(existing)} total)")

with open(PERSISTENT_PATH, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n[OK] 写入完成: kd={len(kd_new)}, lp={len(lp_new)}, bc={len(result.get('behavioral_constraints', []))}")

# Verify
with open(PERSISTENT_PATH) as f:
    verify = json.load(f)
vm = verify.get("memory", {})
print(f"\n回读验证:")
print(f"  key_decisions: {len(vm.get('key_decisions', []))}")
print(f"  learned_patterns: {len(vm.get('learned_patterns', []))}")
print(f"  behavioral_constraints: {len(vm.get('behavioral_constraints', []))}")
print("[OK] 蒸馏完成")
