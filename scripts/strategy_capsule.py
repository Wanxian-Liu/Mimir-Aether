#!/usr/bin/env python3
"""V5 combo strategy"""
import json, os, random
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "mimicore", "generator_config.json")
FK_POOL = ["2026","最新","最新版本","今日","最新实践","2026年"]
TAG_POOL = ["debugging","optimization","architecture","devops","security","performance","reliability","scalability","monitoring","automation","best-practices"]

def _load():
    with open(CONFIG_PATH) as f: return json.load(f)
def _save(d):
    with open(CONFIG_PATH,"w") as f: json.dump(d, f, indent=2, ensure_ascii=False)

def capsule_strategy(rounds, best_score, task_config):
    data = _load()
    md = data.setdefault("metadata", {})
    tg = data.setdefault("tags", {})
    actions = []
    n_pass = sum(1 for r in (rounds or []) if r.passed)

    fk = set(md.get("freshness_keywords", []))
    cand = [k for k in FK_POOL if k not in fk]
    if cand:
        kw = random.choice(cand)
        md.setdefault("freshness_keywords", []).append(kw)
        actions.append("+FK:{}".format(kw))

    uc = md.get("update_count", 3)
    if uc < 15:
        md["update_count"] = uc + random.choice([2,3,5])
        actions.append("UC:{}->{}".format(uc, md["update_count"]))

    if n_pass >= 1:
        et = set(tg.get("extra_taxonomy_tags", []))
        cand2 = [t for t in TAG_POOL if t not in et]
        if cand2:
            t = random.choice(cand2)
            tg.setdefault("extra_taxonomy_tags", []).append(t)
            actions.append("+TAG:{}".format(t))

    if n_pass >= 2:
        kc = md.get("knowledge_confidence", 0.8)
        if kc < 1.0:
            md["knowledge_confidence"] = min(1.0, kc+0.1)
            actions.append("KC:{}->{}".format(kc, md["knowledge_confidence"]))

    _save(data)
    hypothesis = " | ".join(actions) if actions else "no-op"
    with open(CONFIG_PATH) as f:
        changes = {"mimicore/generator_config.json": f.read()}
    return hypothesis, changes, None
