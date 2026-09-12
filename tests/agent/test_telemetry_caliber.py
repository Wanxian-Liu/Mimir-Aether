"""B10（2026-09-13）：遥测双口径 —— 唯一化 + 标注真源/旁路。

背景（根因）：单槽 ``last_context_usage.json`` 是 last-writer-wins。主会话
（``model == config.yaml model.default``，ctx=1M）与旁路实例（如 deepseek-chat，
ctx=163840）**互相覆盖**，读端分不清一个数字属于哪个口径。

本用例锁定四条不变量：
  1. payload 自证口径：``pid`` / ``writer_kind`` / ``caliber``
  2. ``aux`` 不得覆盖未过期 main（TTL 1800s）→ 改写旁路文件
  3. main 始终可覆盖（并回收 stale 旁路）；stale main 可被 aux 接管
  4. 读端标注口径：``caliber_annotation``（+ 存在时的 ``aux`` 块）；prompt 提示带口径
"""

import json
import os
from pathlib import Path

import pytest

import agent.context_usage_snapshot as snap_mod
from agent.context_usage_snapshot import (
    AUX_TTL_SECONDS,
    is_fresh,
    make_caliber,
    resolve_writer_kind,
    write_context_usage_snapshot,
)
from tools import mimir_ops_tool as ops

MAIN_DEFAULT = "deepseek/deepseek-flash"
BYPASS = "deepseek-chat"


def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, default: str = MAIN_DEFAULT) -> Path:
    """隔离 home + config.yaml（``model.default`` 即口径真源）。"""
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        f"model:\n  default: {default}\n", encoding="utf-8"
    )
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(home))
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("MIMIRAETHER_HOME", str(home))
    return home


def _ops_dir(home: Path) -> Path:
    return home / "data" / "ops"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _age(path: Path, seconds: int = AUX_TTL_SECONDS + 60) -> None:
    data = _read(path)
    data["timestamp"] = float(data["timestamp"]) - seconds
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── 1. payload 自证口径 ──────────────────────────────────────────────────────
def test_payload_carries_pid_writer_kind_caliber(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    written = write_context_usage_snapshot(
        prompt_tokens=111,
        completion_tokens=7,
        total_tokens=118,
        context_length=1_000_000,
        threshold_tokens=120_000,
        message_count=3,
        model=MAIN_DEFAULT,
        writer_kind="main",
    )
    assert written is not None and written.name == snap_mod.MAIN_SNAPSHOT_FILENAME
    payload = _read(written)
    assert payload["writer_kind"] == "main"
    assert payload["caliber"] == f"{MAIN_DEFAULT}@1000000/thr=120000"
    assert payload["pid"] == os.getpid()
    assert payload["context_length"] == 1_000_000
    assert payload["threshold_tokens"] == 120_000


def test_make_caliber_format():
    assert make_caliber("m", 1000, 750) == "m@1000/thr=750"
    assert make_caliber("", 0, 0) == "@0/thr=0"


# ── 2. aux 不得覆盖未过期 main ───────────────────────────────────────────────
def test_aux_does_not_clobber_fresh_main(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    main_path = write_context_usage_snapshot(
        prompt_tokens=111_111, context_length=1_000_000, threshold_tokens=120_000,
        model=MAIN_DEFAULT, writer_kind="main",
    )
    before = _read(main_path)

    aux_path = write_context_usage_snapshot(
        prompt_tokens=222_222, context_length=163_840, threshold_tokens=57_344,
        model=BYPASS, writer_kind="aux",
    )

    assert aux_path is not None
    assert aux_path.name == snap_mod.AUX_SNAPSHOT_FILENAME, "未过期 main 被覆盖（唯一化失效）"
    assert _read(main_path) == before, "main 记录被改写了"
    assert _read(aux_path)["prompt_tokens"] == 222_222
    assert _read(aux_path)["writer_kind"] == "aux"
    assert (_ops_dir(home) / snap_mod.AUX_SNAPSHOT_FILENAME).is_file()


# ── 3. main 始终可覆盖（含回收 stale 旁路）──────────────────────────────────
def test_main_overwrites_and_reclaims_stale_aux(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    aux_path = write_context_usage_snapshot(
        prompt_tokens=1, context_length=163_840, model=BYPASS, writer_kind="aux",
    )
    # main 缺失 → aux 接管主槽，同时留旁路档
    assert aux_path.name == snap_mod.MAIN_SNAPSHOT_FILENAME

    main_path = write_context_usage_snapshot(
        prompt_tokens=999, context_length=1_000_000, threshold_tokens=120_000,
        model=MAIN_DEFAULT, writer_kind="main",
    )
    assert _read(main_path)["prompt_tokens"] == 999
    assert _read(main_path)["writer_kind"] == "main"

    aux_file = _ops_dir(home) / snap_mod.AUX_SNAPSHOT_FILENAME
    assert aux_file.is_file(), "未过期的 aux 应保留作旁路证据"

    _age(aux_file)
    assert is_fresh(_read(aux_file)) is False
    write_context_usage_snapshot(
        prompt_tokens=1000, context_length=1_000_000, model=MAIN_DEFAULT, writer_kind="main",
    )
    assert not aux_file.exists(), "stale 旁路文件未被 main 回收"


# ── 3b. stale main 可被 aux 覆盖 ────────────────────────────────────────────
def test_stale_main_can_be_overwritten_by_aux(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    main_path = write_context_usage_snapshot(
        prompt_tokens=111, context_length=1_000_000, model=MAIN_DEFAULT, writer_kind="main",
    )
    _age(main_path)
    assert is_fresh(_read(main_path)) is False

    written = write_context_usage_snapshot(
        prompt_tokens=222, context_length=163_840, model=BYPASS, writer_kind="aux",
    )
    assert written is not None and written.name == snap_mod.MAIN_SNAPSHOT_FILENAME
    payload = _read(main_path)
    assert payload["writer_kind"] == "aux"
    assert payload["prompt_tokens"] == 222
    assert _read(_ops_dir(home) / snap_mod.AUX_SNAPSHOT_FILENAME)["model"] == BYPASS


def test_aux_over_missing_main_takes_main_slot(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    written = write_context_usage_snapshot(
        prompt_tokens=5, context_length=163_840, model=BYPASS, writer_kind="aux",
    )
    assert written.name == snap_mod.MAIN_SNAPSHOT_FILENAME
    assert _read(written)["writer_kind"] == "aux"
    names = {p.name for p in _ops_dir(home).glob("*.json")}
    assert snap_mod.AUX_SNAPSHOT_FILENAME in names
# ── 4. 写者身份判定（main / aux / fail-open）────────────────────────────────
def test_resolve_writer_kind(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    assert resolve_writer_kind(MAIN_DEFAULT) == "main"
    assert resolve_writer_kind(BYPASS) == "aux"
    assert resolve_writer_kind("") == "main"  # 空 model：fail-open

    (home / "config.yaml").unlink()
    assert resolve_writer_kind(BYPASS) == "main", "配置读不到必须 fail-open 判 main"


def test_write_point_uses_resolve_writer_kind(tmp_path, monkeypatch):
    """``agent/callers_mixin.py`` 写点：模型=config 默认 ⇒ main；旁路模型 ⇒ aux。"""
    from agent.callers_mixin import CallersMixin

    class _Comp:
        context_length = 1_000_000
        threshold_tokens = 120_000

        def __init__(self):
            self.ingested = []

        def ingest_usage(self, usage):
            self.ingested.append(usage)

    class _Agent:
        session_id = "sess-1"

        def __init__(self, model):
            self.model = model
            self.compressor = _Comp()

    home = _home(tmp_path, monkeypatch)
    ops_dir = _ops_dir(home)

    main_agent = _Agent(MAIN_DEFAULT)
    CallersMixin._compressor_sync_usage_from_llm(
        main_agent,
        {"usage": {"prompt_tokens": 1000, "completion_tokens": 10}},
        [{"role": "user", "content": "hi"}],
    )
    main_payload = _read(ops_dir / snap_mod.MAIN_SNAPSHOT_FILENAME)
    assert main_payload["writer_kind"] == "main"
    assert main_payload["caliber"] == f"{MAIN_DEFAULT}@1000000/thr=120000"

    aux_agent = _Agent(BYPASS)
    CallersMixin._compressor_sync_usage_from_llm(
        aux_agent,
        {"usage": {"prompt_tokens": 2000, "completion_tokens": 10}},
        [{"role": "user", "content": "hi"}],
    )
    aux_payload = _read(ops_dir / snap_mod.AUX_SNAPSHOT_FILENAME)
    assert aux_payload["writer_kind"] == "aux"
    assert aux_payload["caliber"] == f"{BYPASS}@1000000/thr=120000"
    # 未过期的 main 记录未被这张旁路卡覆盖（唯一化）
    assert _read(ops_dir / snap_mod.MAIN_SNAPSHOT_FILENAME)["prompt_tokens"] == 1000


# ── 5. 读端标注口径 ─────────────────────────────────────────────────────────
def test_reader_annotation_main_only(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    write_context_usage_snapshot(
        prompt_tokens=100, context_length=1_000_000, threshold_tokens=120_000,
        model=MAIN_DEFAULT, writer_kind="main",
    )
    out = json.loads(ops.mimir_ops("context_usage"))
    assert out["ok"] is True
    ann = out["caliber_annotation"]
    assert ann["source"] == "main"
    assert ann["writer_kind"] == "main"
    assert ann["caliber"] == f"{MAIN_DEFAULT}@1000000/thr=120000"
    assert ann["fresh"] is True
    assert ann["ttl_seconds"] == AUX_TTL_SECONDS
    assert "aux" not in ann


def test_reader_annotation_reports_aux_block(tmp_path, monkeypatch):
    home = _home(tmp_path, monkeypatch)
    write_context_usage_snapshot(
        prompt_tokens=100, context_length=1_000_000, threshold_tokens=120_000,
        model=MAIN_DEFAULT, writer_kind="main",
    )
    write_context_usage_snapshot(
        prompt_tokens=163_840, context_length=163_840, threshold_tokens=57_344,
        model=BYPASS, writer_kind="aux",
    )
    out = json.loads(ops.mimir_ops("context_usage"))
    ann = out["caliber_annotation"]
    assert ann["source"] == "main"
    assert "aux" in ann, "旁路文件存在时读端必须报出 aux 块"
    aux_block = ann["aux"]
    assert aux_block["bypass"] is True
    assert aux_block["writer_kind"] == "aux"
    assert aux_block["caliber"] == f"{BYPASS}@163840/thr=57344"
    assert aux_block["context_length"] == 163_840
    assert out["context_usage"]["context_length"] == 1_000_000  # 主口径未被污染


def test_reader_annotation_when_main_missing(tmp_path, monkeypatch):
    _home(tmp_path, monkeypatch)
    out = json.loads(ops.mimir_ops("context_usage"))
    assert out["ok"] is True
    assert out["caliber_annotation"]["caliber"] == make_caliber("", 0, 0)


# ── 5b. prompt 提示带口径 ────────────────────────────────────────────────────
def test_prompt_hint_carries_caliber(tmp_path, monkeypatch):
    from agent.prompt_builder import _build_context_usage_hint

    home = _home(tmp_path, monkeypatch)
    write_context_usage_snapshot(
        prompt_tokens=1, total_tokens=146_807, context_length=1_000_000,
        threshold_tokens=120_000, model=MAIN_DEFAULT, writer_kind="main",
    )
    hint = _build_context_usage_hint()
    assert "146807" in hint
    assert "120000" in hint
    assert f"口径: main({MAIN_DEFAULT}@1000000/thr=120000)" in hint


def test_prompt_hint_marks_bypass_caliber(tmp_path, monkeypatch):
    from agent.prompt_builder import _build_context_usage_hint

    _home(tmp_path, monkeypatch)
    write_context_usage_snapshot(
        prompt_tokens=1, total_tokens=99, context_length=163_840,
        threshold_tokens=57_344, model=BYPASS, writer_kind="aux",
    )
    hint = _build_context_usage_hint()
    assert f"口径: aux({BYPASS}@163840/thr=57344)" in hint


# ── 6. 向后兼容：主槽读取面不变（既有断言依赖）──────────────────────────────
def test_main_read_path_unchanged(tmp_path, monkeypatch):
    from agent.context_usage_snapshot import read_context_usage_snapshot

    _home(tmp_path, monkeypatch)
    assert read_context_usage_snapshot() is None
    write_context_usage_snapshot(
        prompt_tokens=42, context_length=1000, model=MAIN_DEFAULT, writer_kind="main",
    )
    snap = read_context_usage_snapshot()
    assert snap is not None and snap["prompt_tokens"] == 42
