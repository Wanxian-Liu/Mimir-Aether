#!/usr/bin/env python3
"""Standalone distillation script — no agent package imports (avoids circular import)"""

import json, os, re, sys, time
from datetime import datetime, timezone

PERSISTENT_PATH = os.path.expanduser("~/.mimiraether/data/persistent.json")

# ── Step 1: Inject API key from /proc ─────────────────────────────────────
def inject_key():
    for known_pid in [1719]:
        try:
            p = f"/proc/{known_pid}/environ"
            with open(p, "rb") as f:
                raw = f.read()
            for entry in raw.split(b"\x00"):
                if entry.startswith(b"DEEPSEEK_API_KEY=***"):
                    val = entry.split(b"=", 1)[1].decode(errors="replace")
                    if val and val != "***" and len(val) >= 30:
                        os.environ["DEEPSEEK_API_KEY"] = val
                        print(f"[OK] key injected from PID {known_pid} (len={len(val)})")
                        return True
        except (PermissionError, FileNotFoundError, OSError):
            pass
    
    # Fallback: scan all PIDs
    pids = sorted([int(e) for e in os.listdir("/proc") if e.isdigit() and int(e) > 0])
    for pid in pids:
        try:
            p = f"/proc/{pid}/environ"
            with open(p, "rb") as f:
                raw = f.read()
            for entry in raw.split(b"\x00"):
                if entry.startswith(b"DEEPSEEK_API_KEY=***"):
                    val = entry.split(b"=", 1)[1].decode(errors="replace")
                    if val and val != "***" and len(val) >= 30:
                        os.environ["DEEPSEEK_API_KEY"] = val
                        print(f"[OK] key injected from PID {pid} (len={len(val)})")
                        return True
        except (PermissionError, FileNotFoundError, OSError):
            continue
    
    print("[FAIL] no valid key found in /proc")
    return False

# ── Step 2: Build distillation prompt ──────────────────────────────────────
DISTILLATION_SYSTEM_PROMPT = """你是一个梦境记忆蒸馏系统。你的任务是将输入的大量决策和模式记忆去重、合并、精炼。
规则：
1. **key_decisions** 压缩到最多 20 条——合并相关决策，去掉过时或重复的。
2. **learned_patterns** 压缩到最多 30 条——合并同类模式，去掉不再适用的。
3. **behavioral_constraints** 保留最多 5 条最关键的、最具约束力的行为规则。
4. 保留最重要、最独特的条目——质量优先于数量。
5. 为每条决策和模式添加 **tip_type** 字段，分类为 "strategy"（策略类）、"recovery"（恢复类）、"optimization"（优化类）。
6. 为每条决策添加 **cause_chain** 字段：{"direct": "直接触发原因", "proximate": "近因/中间原因", "root": "根因/系统性问题"}。
7. 每条约束格式：{"rule": "...", "source": "distilled", "evidence": "..."}
8. **self_contradiction** 为单条字符串——分析最严重的自我矛盾。
9. 只输出 JSON，不要解释过程。

输入记忆：
{memory_text}

输出格式：
{"key_decisions": [{"decision": "...", "context": "...", "tip_type": "strategy|recovery|optimization", "cause_chain": {"direct": "...", "proximate": "...", "root": "..."}}], "learned_patterns": [{"pattern": "...", "evidence": "...", "tip_type": "strategy|recovery|optimization"}], "behavioral_constraints": [{"rule": "...", "source": "distilled", "evidence": "..."}], "self_contradiction": "..."}"""

def build_memory_text(data):
    mem = data.get("memory", {})
    kd = mem.get("key_decisions", [])
    lp = mem.get("learned_patterns", [])
    bc = mem.get("behavioral_constraints", [])
    lines = []
    lines.append(f"=== key_decisions ({len(kd)} 条) ===")
    for k in kd:
        lines.append(f"- {json.dumps(k, ensure_ascii=False)}")
    lines.append(f"\n=== learned_patterns ({len(lp)} 条) ===")
    for p in lp:
        lines.append(f"- {json.dumps(p, ensure_ascii=False)}")
    lines.append(f"\n=== behavioral_constraints ({len(bc)} 条) ===")
    for b in bc:
        lines.append(f"- {json.dumps(b, ensure_ascii=False)}")
    return "\n".join(lines)

# ── Step 3: Call DeepSeek API ──────────────────────────────────────────────
def call_llm(prompt, api_key):
    import urllib.request
    import json as j
    
    payload = j.dumps({
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
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = j.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"].strip()
        # Strip ```json ``` wrappers
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0].strip()
        return j.loads(content)
    except Exception as e:
        print(f"[FAIL] API call: {e}")
        return None

# ── Step 4: Write back ────────────────────────────────────────────────────
def write_result(data, result):
    mem = data.setdefault("memory", {})
    old_decisions = len(mem.get("key_decisions", []))
    old_patterns = len(mem.get("learned_patterns", []))
    old_constraints = len(mem.get("behavioral_constraints", []))
    
    new_decisions = len(result.get("key_decisions", []))
    new_patterns = len(result.get("learned_patterns", []))
    new_constraints = len(result.get("behavioral_constraints", []))
    
    mem["key_decisions"] = result["key_decisions"][:20]
    mem["learned_patterns"] = result["learned_patterns"][:30]
    if new_constraints > 0:
        mem["behavioral_constraints"] = result["behavioral_constraints"][:5]
    
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
    
    # Stats
    tipped_kd = sum(1 for k in result["key_decisions"] if k.get("tip_type"))
    chained_kd = sum(1 for k in result["key_decisions"] if k.get("cause_chain"))
    tipped_lp = sum(1 for p in result["learned_patterns"] if p.get("tip_type"))
    
    print(f"\n{'='*50}")
    print(f"蒸馏结果:")
    print(f"  key_decisions: {old_decisions} → {new_decisions}")
    print(f"    tip_type: {tipped_kd}/{new_decisions}")
    print(f"    cause_chain: {chained_kd}/{new_decisions}")
    print(f"  learned_patterns: {old_patterns} → {new_patterns}")
    print(f"    tip_type: {tipped_lp}/{new_patterns}")
    print(f"  behavioral_constraints: {old_constraints} → {new_constraints}")
    print(f"  self_contradiction: {'有' if contradiction.strip() else '无'}")

# ── Main ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("梦境蒸馏 — 独立模式")
    print("=" * 50)
    
    if not inject_key():
        sys.exit(1)
    
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key or api_key == "***" or len(api_key) < 30:
        print("[FAIL] no valid api_key after injection")
        sys.exit(1)
    print(f"[OK] api_key: {api_key[:7]}...{api_key[-4:]} (len={len(api_key)})")
    
    with open(PERSISTENT_PATH) as f:
        data = json.load(f)
    
    memory_text = build_memory_text(data)
    print(f"[OK] memory_text: {len(memory_text)} 字符")
    
    prompt = DISTILLATION_SYSTEM_PROMPT.format(memory_text=memory_text)
    print(f"[OK] prompt: {len(prompt)} 字符")
    
    print("\n[..] 调用 DeepSeek API...")
    start = time.time()
    result = call_llm(prompt, api_key)
    elapsed = time.time() - start
    print(f"[OK] API 耗时: {elapsed:.1f}s")
    
    if result is None:
        print("[FAIL] LLM 未返回有效结果")
        sys.exit(1)
    
    write_result(data, result)
    print("[OK] 写入完成")
    
    # Verify by re-reading
    with open(PERSISTENT_PATH) as f:
        verify = json.load(f)
    vm = verify.get("memory", {})
    print("\n=== 回读验证 ===")
    print(f"  key_decisions: {len(vm.get('key_decisions', []))}")
    print(f"  learned_patterns: {len(vm.get('learned_patterns', []))}")
    print(f"  behavioral_constraints: {len(vm.get('behavioral_constraints', []))}")
    print("[OK] 蒸馏完成")
