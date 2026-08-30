"""手动触发梦境蒸馏（供终端使用）。"""
import os, sys, json

# 从 .env 加载 DEEPSEEK_API_KEY
env_path = os.environ.get("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether")) + "/.env"
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if line.startswith("DEEPSEEK_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            os.environ["DEEPSEEK_API_KEY"] = key
            break

sys.path.insert(0, os.environ.get("MIMIR_REPO_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent.dream_memory import sync_run_dream_cycle, _get_persistent_path, _load_persistent

# 跑之前状态
p = _get_persistent_path()
data = _load_persistent(p)
mem = data.get("memory", {})
print(f"路径: {p}")
print(f"蒸馏前: kd={len(mem.get('key_decisions',[]))}条, lp={len(mem.get('learned_patterns',[]))}条, bc={len(mem.get('behavioral_constraints',[]))}条")

# 执行蒸馏
report = sync_run_dream_cycle(dry_run=False)
print(f"\n{report}")

# 跑之后状态
data2 = _load_persistent(p)
mem2 = data2.get("memory", {})
kd2 = mem2.get("key_decisions", [])
lp2 = mem2.get("learned_patterns", [])
bc2 = mem2.get("behavioral_constraints", [])
print(f"\n蒸馏后: kd={len(kd2)}条 (cause={sum(1 for k in kd2 if 'cause_chain' in k)}, tip={sum(1 for k in kd2 if 'tip_type' in k)})")
print(f"         lp={len(lp2)}条 (cause={sum(1 for p in lp2 if 'cause_chain' in p)}, tip={sum(1 for p in lp2 if 'tip_type' in p)})")
print(f"         bc={len(bc2)}条")
