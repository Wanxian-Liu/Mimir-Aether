"""A8 尾巴 · signal-deliver.py 单点迁移回归（2026-09-18 · 收件行 166）

四臂（受控）：
  ① 静态委托：脚本必须 import buzz_send 且走 append_envelope()，代码里不得再有 canonical 收件箱字面量
     （AST 口径，与 E7 审计器同源：audit.scan_file(...)["writes_canonical"] is False）。
  ② 行为孪生：隔离箱实跑（env BUZZ_INBOX_HERMES -> tmp）⇒ rc=0、末行可解析、
     原 10 键**逐键保留** + kind 属 U2 枚举（载荷不变，仅新增契约字段）。
  ③ 负控：② 期间真实 hermes 箱 size/mtime_ns 未变（证明隔离有效，非写进了真箱）。
  ④ 回归钉：本仓 scripts/ 下 writers_bypassing == []（E7 判据不许回漂）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
SCRIPT = SCRIPTS / "signal-deliver.py"
sys.path.insert(0, str(SCRIPTS))
import buzz_send  # noqa: E402  （单一真源：canonical 目录由发件端单点决定）

REAL_BOX = buzz_send.CANONICAL_DIR / "buzz-inbox-hermes.jsonl"

ORIG_KEYS = ("ts", "id", "from", "to", "type", "content", "task", "summary", "discussion", "commit")


def _load_audit():
    path = SCRIPTS / "audit_send_paths.py"
    spec = importlib.util.spec_from_file_location("audit_send_paths_under_test_a8tail", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_script_delegates_to_single_point():
    """① 静态：已委托单点，且不再是 canonical 写路径。"""
    audit = _load_audit()
    res = audit.scan_file(SCRIPT)
    src = SCRIPT.read_text(encoding="utf-8")
    assert "import buzz_send" in src, "未委托单点"
    assert "buzz_send.append_envelope(" in src, "未走低层追加入口"
    assert res["writes_canonical"] is False, res
    assert res["delegated"] is True, res
    assert res["bad"] == [] and res["canonical"] == [], res


def test_payload_preserved_and_isolated(tmp_path):
    """② 行为孪生 + ③ 负控：载荷 10 键保留、写 tmp 箱、真箱零接触。"""
    box = tmp_path / "buzz-inbox-hermes.jsonl"
    before = (REAL_BOX.stat().st_size, REAL_BOX.stat().st_mtime_ns) if REAL_BOX.exists() else None

    env = dict(os.environ)
    env["BUZZ_INBOX_HERMES"] = str(box)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "A8tail", "迁移验收", "/tmp/card.md", "deadbeef"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)

    assert box.exists(), f"隔离箱未生成：{proc.stdout}"
    lines = box.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, lines
    env_rec = json.loads(lines[-1])
    for key in ORIG_KEYS:
        assert key in env_rec, f"载荷键丢失: {key}（{sorted(env_rec)}）"
    assert env_rec["kind"] == 9, env_rec
    assert env_rec["content"].startswith("@hermes 【Mimir完成】"), env_rec["content"]
    assert env_rec["to"] == "hermes" and env_rec["commit"] == "deadbeef"

    after = (REAL_BOX.stat().st_size, REAL_BOX.stat().st_mtime_ns) if REAL_BOX.exists() else None
    assert after == before, f"负控失败：真实箱被写（before={before} after={after}）"


def test_no_writer_bypasses_in_repo_after_migration():
    """④ 回归钉：本仓 scripts/ writers_bypassing 必须为 0。"""
    audit = _load_audit()
    res = audit.scan(SCRIPTS)
    assert res["writers_bypassing"] == [], res["writers_bypassing"]
    assert res["violations"] == [], res["violations"]
