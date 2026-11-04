"""死脚本闸回归用例（2026-11-04 · 矛盾报告写入端 3 份拷贝收口）。

背景：`scripts/distill_direct.py` 与 `scripts/run_distillation_standalone.py`
是梦境蒸馏的历史入口，**零引用**（cron 走 `scripts/run_dream_distillation.py`
→ `agent.dream_memory.sync_run_dream_cycle`），但仍写**旧语义**的
`data/self_contradiction_report.json`。跑一次就会把 2026-11-03 的去重修复抹掉。

两向：
- 正控：两个死脚本必须**被拦住**（rc=2 + 明确提示），不能只是注释。
- 负控：活体入口 `run_dream_distillation.py` 必须**不被拦**（否则蒸馏停摆）。

第三项是「不许复活」：如果谁把死脚本重新接回调用链，本用例必须变红。
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
DEAD = ["distill_direct.py", "run_distillation_standalone.py"]
LIVE = "run_dream_distillation.py"


def _run(name):
    return subprocess.run([sys.executable, str(SCRIPTS / name)],
                          capture_output=True, text=True, timeout=60)


def test_positive_dead_scripts_are_blocked():
    """正控：两个死脚本被拦住，rc=2，且**说清为什么**（不静默）。"""
    for name in DEAD:
        r = _run(name)
        assert r.returncode == 2, "%s 未被拦住: rc=%s out=%r" % (name, r.returncode, r.stdout[:200])
        assert "DEAD-SCRIPT" in r.stderr, "%s 缺少 DEAD-SCRIPT 标记: %r" % (name, r.stderr[:200])
        assert "self_contradiction_report.json" in r.stderr, "%s 未说明污染对象" % name


def test_negative_live_entry_not_blocked():
    """负控：活体入口不得带死脚本闸（带上 = 蒸馏直接停摆）。"""
    text = (SCRIPTS / LIVE).read_text(encoding="utf-8")
    assert "DEAD-SCRIPT" not in text
    assert "sync_run_dream_cycle" in text, "活体入口变了，本用例前提失效，请复核"


def test_no_live_reference_to_dead_scripts():
    """不许复活：调用链里不得再引用这两个死脚本（自身定义除外）。

    匹配用**模块名（去 .py）**而不是文件名 —— 真实引用形态多是
    `import distill_direct` / `from scripts import distill_direct`，
    带 `.py` 的字面量反而少。用带后缀匹配 = 漏检（本用例首版即此坑，
    造违例仍 PASS，属假绿口）。
    """
    stems = [n[:-3] for n in DEAD]
    hits = []
    for p in REPO.rglob("*.py"):
        s = str(p)
        if any(x in s for x in ("/.venv/", "/.git/", "/.crew/", "/backups/")):
            continue
        if p.name in ("test_dead_distill_scripts.py",) or p.name in DEAD:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for stem in stems:
            if stem in txt:
                hits.append("%s → %s" % (s.replace(str(REPO) + "/", ""), stem))
    assert not hits, "死脚本被重新引用（会写旧语义）: %s" % hits
