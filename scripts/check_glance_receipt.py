#!/usr/bin/env python3
"""GLANCE 已读回执 · 两向判据（AGENTS §8.5 判据形态 1「脚本」）。

判据语义（receipt 复算数字 同款）：
  E2_positive == 'GLANCE'  正控：干净环境 + load_hermes_dotenv（产线同一加载路径）
  E2_negative == ''        负控：显式 MIMIR_FEISHU_REACTION_READ=off
  E1_proc_hits >= 1        活体：运行中 gateway 的 /proc/<MainPID>/environ 含 =GLANCE
  E3_glance_lines >= 1     端到端：agent.log 有 'reaction added GLANCE on <mid> ok'（真实入站）
  IMPORT_OK  == True       活体件可被 import（注释改动未破件）

rc：0 = 全过；3 = PENDING（E3 尚无真实入站，其余全过）；1 = 拦（正/负控或 E1 不过）
用法：.venv/bin/python3 scripts/check_glance_receipt.py [--selftest]
"""
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
REPO = HOME / "src" / "MimirAether"
MIMIR_HOME = HOME / ".mimiraether"
LOG = MIMIR_HOME / "logs" / "agent.log"
PY = str(REPO / ".venv" / "bin" / "python3")
PROBE = str(MIMIR_HOME / "tmp" / "probe_reaction_read.py")
UNIT = "mimiraether.service"
E3_RE = re.compile(r"^\S+ \S+ INFO gateway\.platforms\.feishu_adapter: "
                   r"\[Feishu\] reaction added GLANCE on \S+ ok$", re.M)


def parse_probe(out: str, key: str = "REACTION_READ"):
    m = re.search(rf"FeishuAdapter\.{key}\s*=\s*(\S+)", out)
    return m.group(1) if m else "<parse-error>"


def run_probe(extra: dict):
    env = {"HOME": str(HOME), "MIMIR_AETHER_HOME": str(MIMIR_HOME)}
    env.update(extra)
    return subprocess.run([PY, PROBE], capture_output=True, text=True, env=env).stdout


def main() -> int:
    positive = parse_probe(run_probe({}))
    negative = parse_probe(run_probe({"MIMIR_FEISHU_REACTION_READ": "off"}))

    pid = subprocess.run(["systemctl", "--user", "show", "-p", "MainPID", "--value", UNIT],
                         capture_output=True, text=True).stdout.strip()
    try:
        hits = Path(f"/proc/{pid}/environ").read_bytes().count(b"MIMIR_FEISHU_REACTION_READ=GLANCE")
    except Exception:  # noqa: BLE001
        hits = -1

    txt = LOG.read_text(errors="replace") if LOG.exists() else ""
    e3 = len(E3_RE.findall(txt))

    sys.path.insert(0, str(REPO))
    try:
        import gateway.work_status  # noqa: F401
        import_ok = True
    except Exception:  # noqa: BLE001
        import_ok = False

    print(f"E2_positive={positive}")
    print(f"E2_negative={negative!r}")
    print(f"E1_proc_hits={hits}  (MainPID={pid})")
    print(f"E3_glance_lines={e3}")
    print(f"IMPORT_OK={import_ok}")

    hard = (positive == "GLANCE" and negative == "''" and hits >= 1 and import_ok)
    if not hard:
        print("VERDICT=FAIL")
        return 1
    if e3 == 0:
        print("VERDICT=PENDING (无真实入站消息；等下一次飞书入站)")
        return 3
    print("VERDICT=PASS")
    return 0


def selftest() -> int:
    ok = (E3_RE.search("2026-10-11 12:00:00,001 INFO gateway.platforms.feishu_adapter: "
                       "[Feishu] reaction added GLANCE on om_x1 ok") is not None)
    neg = (E3_RE.search("2026-10-11 12:00:00,001 INFO gateway.platforms.feishu_adapter: "
                        "[Feishu] reaction added DONE on om_x1 ok") is None)
    print(f"selftest positive={ok} negative={neg}")
    return 0 if (ok and neg) else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
