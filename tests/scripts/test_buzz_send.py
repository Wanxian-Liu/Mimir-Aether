r"""C 组 C4 · buzz_send.py（四方信箱发件端单点）守卫 + 回写校验（Gate2 登记候选）。

覆盖的判据（全部来自盘上事故，不是想象）：
  * **双重编码守卫**：`card` 含字面 `\uXXXX` / `\/` ⇒ 拒绝。历史事故：三箱各有 1 行
    `card` 字段里是二次转义的 JSON 文本 ⇒ 机器按字段取路径取不到（人工读正文却看不出）。
  * **信封契约**：`content` 不得为空、`kind` 必须在枚举内（U2）。
  * **回写校验**：落盘后末行必须可解析且 `id` 与本次一致，否则抛错 ——「写了」≠「写对了」。
  * **追加语义**：不重写既有行（POSIX O_APPEND 并发安全的前提）；中文不转义（ensure_ascii=False）。
  * **幽灵路径 `card`**：只告警不阻断（卡可能尚未落盘、或已被归档）。
  * **CLI**：坏 `card` ⇒ 退出码 2（REFUSED）且不落盘。
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import buzz_send as bs  # noqa: E402

# 字面转义序列（\uXXXX / \/）——真中文路径不可能含它们
BAD_CARD = "/home/rayliu/wiki/discussions/2026-09-16-" + "\\u56db" + "\\u65b9" + ".md"
BAD_CARD_SLASH = "/home/rayliu/wiki/discussions/a" + "\\/" + "b.md"


REAL_CANONICAL = Path("/home/rayliu/.openclaw/data")


@pytest.fixture(autouse=True)
def _isolate_real_boxes(tmp_path, monkeypatch):
    """硬闸：任何测试都不得写进**真实**四方信箱。

    事故来源（2026-09-16 · C4 自曝）：第一版本 fixture 用 `monkeypatch.setenv("BUZZ_INBOX_DIR", …)`
    想隔离落点，但 `CANONICAL_DIR` 是 **import 时**读 env 的模块常量 ⇒ patch 无效，
    于是 6 行测试信封真的落进了 **hermes 箱**（已隔离到
    `~/.mimiraether/repairs/20260916-test-pollution/` 并从活箱移除）。
    修法：patch 模块常量 + 清掉所有 `BUZZ_INBOX_*` 覆盖 + **收尾比对真实箱 mtime**（变了就 fail）。
    """
    monkeypatch.setattr(bs, "CANONICAL_DIR", tmp_path)
    for var in [v for v in list(os.environ) if v.startswith("BUZZ_INBOX_")]:
        monkeypatch.delenv(var, raising=False)
    before = {f: f.stat().st_mtime_ns for f in REAL_CANONICAL.glob("buzz-inbox-*.jsonl")}
    yield
    after = {f: f.stat().st_mtime_ns for f in REAL_CANONICAL.glob("buzz-inbox-*.jsonl")}
    assert before == after, "测试写进了真实四方信箱——隔离失效（见 2026-09-16 事故）"


@pytest.fixture()
def inbox(tmp_path, monkeypatch):
    # ⚠️ 盘上事实：`CANONICAL_DIR` 在 **import 时**读 `BUZZ_INBOX_DIR` ⇒ 事后 setenv 无效，
    # 必须直接改模块常量（这本身是一条「配置只在 import 生效」的可测性缺陷，已记入 C4 交付卡）。
    monkeypatch.setattr(bs, "CANONICAL_DIR", tmp_path)
    monkeypatch.delenv("BUZZ_INBOX_HERMES", raising=False)
    monkeypatch.setenv("BUZZ_SENDER", "mimir")
    return tmp_path / "buzz-inbox-hermes.jsonl"


def _lines(path: Path):
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


# --------------------------------------------------------------- 双重编码守卫


def test_validate_card_rejects_literal_unicode_escape():
    with pytest.raises(ValueError) as exc:
        bs.validate_card(BAD_CARD)
    assert "双重编码" in str(exc.value)


def test_validate_card_rejects_literal_escaped_slash():
    with pytest.raises(ValueError):
        bs.validate_card(BAD_CARD_SLASH)


def test_validate_card_rejects_empty_and_non_string():
    with pytest.raises(ValueError):
        bs.validate_card("   ")
    with pytest.raises(ValueError):
        bs.validate_card(123)  # type: ignore[arg-type]


def test_validate_card_passes_plain_path():
    value, warnings = bs.validate_card("/tmp/does-not-exist-card.md")
    assert value == "/tmp/does-not-exist-card.md"
    assert warnings and "不存在" in warnings[0]  # 幽灵路径只告警


def test_validate_card_no_warning_for_existing_path(tmp_path):
    real = tmp_path / "real-card.md"
    real.write_text("x", encoding="utf-8")
    value, warnings = bs.validate_card(str(real))
    assert value == str(real) and warnings == []


def test_validate_card_allows_relative_pointer_without_fs_check():
    """相对写法（wiki/discussions/…）不做存在性判定——避免把『还没落盘』误判成坏指针。"""
    value, warnings = bs.validate_card("wiki/discussions/foo.md")
    assert value == "wiki/discussions/foo.md" and warnings == []


# --------------------------------------------------------------- 信封契约


def test_envelope_rejects_empty_content():
    with pytest.raises(ValueError):
        bs.build_envelope("hermes", "   ")


def test_envelope_rejects_unknown_kind():
    with pytest.raises(ValueError):
        bs.build_envelope("hermes", "正文", kind=42)


# --------------------------------------------------------------- 落盘与回写校验


def test_send_appends_and_preserves_existing_lines(inbox):
    bs.send("hermes", "第一条", kind=2)
    bs.send("hermes", "第二条", kind=2)
    rows = _lines(inbox)
    assert [r["content"] for r in rows] == ["第一条", "第二条"]


def test_send_writes_unescaped_utf8(inbox):
    bs.send("hermes", "中文正文：四方通信", kind=2, card="/tmp/ghost.md")
    raw = inbox.read_text(encoding="utf-8")
    assert "中文正文" in raw
    assert "\\u" not in raw  # 落盘原文里不得出现字面转义序列


def test_send_returns_verified_flag_and_line_count(inbox):
    res = bs.send("hermes", "正文", kind=2)
    assert res["written"] is True and res["verified"] is True
    assert res["lines"] == 1 and Path(res["path"]) == inbox


def test_send_refuses_double_encoded_card_and_writes_nothing(inbox):
    with pytest.raises(ValueError):
        bs.send("hermes", "正文", kind=2, card=BAD_CARD)
    assert not inbox.exists()


def test_send_raises_when_readback_id_mismatch(inbox, monkeypatch):
    """回写校验的负控：落盘行与本次信封不一致时必须抛错（模拟『写坏了』）。"""
    real_dumps = json.dumps

    def _forged_dumps(env, **kw):
        forged = dict(env)
        forged["id"] = "forged-id"
        return real_dumps(forged, **kw)

    fake = types.SimpleNamespace(
        dumps=_forged_dumps, loads=json.loads, JSONDecodeError=json.JSONDecodeError
    )
    monkeypatch.setattr(bs, "json", fake)
    with pytest.raises(RuntimeError) as exc:
        bs.send("hermes", "正文", kind=2)
    assert "回写校验失败" in str(exc.value)


def test_dry_run_does_not_write(inbox):
    res = bs.send("hermes", "正文", kind=2, dry_run=True)
    assert res["written"] is False and not inbox.exists()


# --------------------------------------------------------------- CLI 面


def test_cli_refuses_bad_card_with_exit_2(inbox, capsys):
    code = bs.main(["--to", "hermes", "--kind", "2", "--content", "x", "--card", BAD_CARD])
    assert code == 2
    assert "REFUSED" in capsys.readouterr().err
    assert not inbox.exists()


def test_cli_reports_warning_for_ghost_card(inbox, capsys):
    code = bs.main(["--to", "hermes", "--kind", "2", "--content", "x",
                    "--card", "/tmp/definitely-missing-card.md"])
    assert code == 0
    assert "WARN" in capsys.readouterr().err
    assert _lines(inbox)[0]["card"] == "/tmp/definitely-missing-card.md"


# --------------------------------------------------------------- 落点解析


def test_resolve_inbox_uses_canonical_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "CANONICAL_DIR", tmp_path)
    monkeypatch.delenv("BUZZ_INBOX_LOKI", raising=False)
    assert bs.resolve_inbox("loki") == tmp_path / "buzz-inbox-loki.jsonl"


def test_resolve_inbox_per_recipient_override(tmp_path, monkeypatch):
    monkeypatch.setattr(bs, "CANONICAL_DIR", tmp_path / "canonical")
    monkeypatch.setenv("BUZZ_INBOX_HERMES", str(tmp_path / "custom.jsonl"))
    assert bs.resolve_inbox("hermes") == tmp_path / "custom.jsonl"
