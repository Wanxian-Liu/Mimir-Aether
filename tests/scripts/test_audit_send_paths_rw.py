"""E7 · 发件单点闸（2026-09-16）：把「新增脚本不得自造收件箱路径」变成可回归判据。

三类判据：
  ① 单点必须暴露低层追加入口 append_envelope（迁移 enabler；否则历史脚本只能被强制重塑信封）。
  ② **读写分流**要有鉴别力：writer 夹具 → writers_bypassing=1；reader 夹具 → reader_only=1
     （旧口径把纯读取件也算「未走单点发件」= 判据失真，本测试即其回归）。
  ③ 本仓 scripts/ 下 **writers_bypassing 必须为 0**（防未来新增硬编码写路径）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _load_audit():
    path = SCRIPTS / "audit_send_paths.py"
    spec = importlib.util.spec_from_file_location("audit_send_paths_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


WRITER_FIXTURE = '''import json
BOX = "~/.openclaw/data/buzz-inbox-hermes.jsonl"
with open(BOX, "a", encoding="utf-8") as f:
    f.write(json.dumps({"content": "x", "kind": 2}) + "\\n")
'''

READER_FIXTURE = '''BOX = "~/.openclaw/data/buzz-inbox-hermes.jsonl"
with open(BOX, encoding="utf-8") as f:
    lines = f.read().splitlines()
'''


def test_append_envelope_exposed(tmp_path, monkeypatch):
    """① 单点必须提供低层追加入口（迁移/未来脚本共用）。"""
    sys.path.insert(0, str(SCRIPTS))
    import buzz_send

    monkeypatch.setattr(buzz_send, "CANONICAL_DIR", tmp_path)

    assert callable(buzz_send.append_envelope)
    assert callable(buzz_send.resolve_inbox)
    res = buzz_send.append_envelope("hermes", {"content": "hi", "kind": 2})
    assert res["written"] is True and res["verified"] is True
    assert (tmp_path / "buzz-inbox-hermes.jsonl").exists()


def test_classifier_splits_writer_and_reader(tmp_path):
    """② 读写分流必须有鉴别力（否则 writer 面数字没有意义）。"""
    audit = _load_audit()
    (tmp_path / "w.py").write_text(WRITER_FIXTURE, encoding="utf-8")
    (tmp_path / "r.py").write_text(READER_FIXTURE, encoding="utf-8")
    res = audit.scan(tmp_path)
    assert len(res["writers_bypassing"]) == 1, res
    assert res["writers_bypassing"][0]["file"] == "w.py"
    assert len(res["reader_only"]) == 1, res
    assert res["reader_only"][0]["file"] == "r.py"


def test_no_writer_bypasses_single_point_in_repo():
    """③ 本仓 scripts/ 下不得有绕过单点的**写入**（防新增漂移）。"""
    audit = _load_audit()
    res = audit.scan(SCRIPTS)
    assert res["writers_bypassing"] == [], (
        "新增了硬编码收件箱写路径，请改用 buzz_send.send() / append_envelope()："
        f"{res['writers_bypassing']}"
    )


def test_dead_path_is_still_violation(tmp_path):
    """④ 负控：死路径（.buzz-nostr/state、/tmp）必须仍判 violation —— 收窄 CANONICAL_MARKERS 不得放行死路径。"""
    audit = _load_audit()
    (tmp_path / "dead.py").write_text(
        'P = "~/.buzz-nostr/state/buzz-inbox-hermes.jsonl"\n'
        'Q = "/tmp/buzz-inbox-hermes.jsonl"\n', encoding="utf-8")
    res = audit.scan(tmp_path)
    assert len(res["violations"]) == 2, res
