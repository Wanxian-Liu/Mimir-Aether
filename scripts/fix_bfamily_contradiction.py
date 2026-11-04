#!/usr/bin/env python3
"""消除 B 族自我矛盾：给「可逆我定/不可逆上收」加作用域限定词。

背景：梦境蒸馏 11-02 / 11-03 连续报同一条"矛盾"——
  决策「可逆的我定、不可逆的上收」 vs 模式「风险须升级为 owner+deadline」
  报告器读法：「可逆决策既被授权自主又被要求上收」

裁定：**两条正交**。决策条管"谁拍板"，模式条管"怎么记账"。
「我定」= owner 是我，不是 owner 空缺。给决策条补限定词即可消灭该族。

用法：
  fix_bfamily_contradiction.py          # 应用修复（先备份，经 facade 单写窗口）
  fix_bfamily_contradiction.py --check  # 只读校验，不写盘

退出码：0 = 状态符合预期；1 = 不符 / 失败（stderr 带 B-FAMILY-FIX 标记）
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone

MARK = "B-FAMILY-FIX"

# 决策条：原句 → 加作用域限定
DEC_PREFIX = "交付风格：给「建议+我负责执行到底」，可逆的我定、不可逆的上收；汇报先结论后证据"
DEC_NEW = (
    DEC_PREFIX
    + "。两条均须落 owner+deadline（或断言/门禁），差别只在 owner 是谁："
    "可逆时 owner 是我（Mimir），不可逆时是刘哥——「我定」≠「不记账」，"
    "故与「风险须升级为 owner+deadline」不冲突"
)

# 模式条：补括注，明示 owner 可为自身
PAT_PREFIX = "风险须升级为 owner+deadline 或断言/门禁，禁只写「已知未知·不阻塞」"
PAT_ADD = "（owner 可为自身：可逆事项下 owner 即 Mimir，仍须给 deadline 或落成断言/门禁）"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_home() -> str:
    """真实用户 home——不受 HOME 环境变量污染（沙箱里 HOME=~/.mimiraether）。"""
    try:
        import pwd

        return pwd.getpwuid(os.getuid()).pw_dir
    except Exception:  # pragma: no cover
        return os.path.expanduser("~")


def persist_path() -> str:
    return os.path.join(user_home(), ".mimiraether", "memory", "persistent.json")


def fail(stage: str, detail: str) -> int:
    sys.stderr.write(f"{MARK} stage={stage} {detail}\n")
    sys.stderr.flush()
    print(f"{MARK} FAILED stage={stage} {detail}")
    return 1


def inspect(path: str) -> tuple[bool, bool, int]:
    """返回 (dec_ok, pat_ok, matched)_"""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    mem = d.get("memory", {})
    dec = [
        x for x in mem.get("key_decisions", [])
        if isinstance(x, dict) and str(x.get("decision", "")).startswith(DEC_PREFIX)
    ]
    pat = [
        p for p in mem.get("learned_patterns", [])
        if isinstance(p, dict) and str(p.get("pattern", "")).startswith(PAT_PREFIX)
    ]
    dec_ok = (
        len(dec) == 1
        and "owner 是我" in dec[0]["decision"]
        and "≠「不记账」" in dec[0]["decision"]
    )
    pat_ok = len(pat) == 1 and "owner 可为自身" in pat[0]["pattern"]
    return dec_ok, pat_ok, len(dec)


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    path = persist_path()
    if not os.path.isfile(path):
        return fail("precheck", f"missing {path}")

    if check_only:
        try:
            dec_ok, pat_ok, n = inspect(path)
        except Exception as e:  # noqa: BLE001
            return fail("read", f"{type(e).__name__}: {e}")
        print(f"path   : {path}")
        print(f"matched: dec={n}")
        print(f"dec_ok={dec_ok} pat_ok={pat_ok}")
        if dec_ok and pat_ok:
            print(f"{MARK} CHECK-OK")
            return 0
        return fail("check", f"dec_ok={dec_ok} pat_ok={pat_ok}")

    # ① 写前备份
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bdir = os.path.join(user_home(), ".mimiraether", "data", "backups", f"bfamily-{ts}")
    os.makedirs(bdir, exist_ok=True)
    bpath = os.path.join(bdir, "persistent.json")
    shutil.copy2(path, bpath)
    print(f"backup: {bpath} ({os.path.getsize(bpath)} B)")

    sys.path.insert(0, REPO)
    os.chdir(REPO)
    from agent.memory_write_facade import write_persistent_mutator

    hits = {"dec": 0, "pat": 0}

    def mutator(d: dict) -> None:
        mem = d.setdefault("memory", {})
        for x in mem.get("key_decisions", []):
            if isinstance(x, dict) and str(x.get("decision", "")).startswith(DEC_PREFIX):
                x["decision"] = DEC_NEW
                hits["dec"] += 1
        for p in mem.get("learned_patterns", []):
            if isinstance(p, dict) and str(p.get("pattern", "")).startswith(PAT_PREFIX):
                if PAT_ADD not in p["pattern"]:
                    p["pattern"] = p["pattern"] + PAT_ADD
                    hits["pat"] += 1

    try:
        write_persistent_mutator(mutator)
    except Exception as e:  # noqa: BLE001
        return fail("write", f"{type(e).__name__}: {e}")

    if hits["dec"] == 0:
        return fail("apply", "decision not matched (already changed?)")

    # ③ 读回验证
    dec_ok, pat_ok, _ = inspect(path)
    print(f"hits: dec={hits['dec']} pat={hits['pat']}")
    print(f"verify: dec_ok={dec_ok} pat_ok={pat_ok}")
    if not (dec_ok and pat_ok):
        return fail("verify", f"dec_ok={dec_ok} pat_ok={pat_ok}")
    print(f"{MARK} OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
