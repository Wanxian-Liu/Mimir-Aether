"""RS21 · 蒸馏写回必须同步刷新 memory/ 镜像（2026-10-31 · Mimir 席根治）

根因（实测读数 2026-10-31）:
    data/persistent.json      mtime 23:01:14   sha 7c4deaff  (蒸馏写的)
    data/persistent.json.bak  mtime 21:21:04   sha 0a784304
    memory/persistent.json    mtime 21:21:04   sha b4d421ef  ← 停在上一次主路径保存
⇒ dream_memory._save_persistent() 裸 open("w")，绕过 persistent_store._save_unlocked
   ⇒ 不刷 .bak、不触发 _dual_write_mirror ⇒ 健康检查 R8 dual-write DRIFT 红。

两向判据（AGENTS §9 档位④）：
  正控：目标 == 默认持久化路径 ⇒ 镜像必须存在，且字节与主库**一致**（不是「有字段」）
  负控：显式非默认路径（临时/测试文件）⇒ 不得产生任何镜像（不许污染 memory/）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent import dream_memory as dm
from agent import persistent_store as ps


def _data():
    return {
        "memory": {
            "key_decisions": [{"decision": "先落盘再汇报"}],
            "learned_patterns": [{"pattern": "盘上读数高于自述"}],
            "behavioral_constraints": [],
        }
    }


def _patch_paths(monkeypatch, data_path: Path, mirror: Path) -> None:
    monkeypatch.setattr(ps, "get_persistent_path", lambda: data_path)
    monkeypatch.setattr(ps, "get_memory_persistent_path", lambda: mirror)


def test_default_path_write_mirrors_byte_identical(tmp_path, monkeypatch):
    """正控：默认路径写盘 ⇒ 镜像存在且与主库字节一致。"""
    data_path = tmp_path / "data" / "persistent.json"
    mirror = tmp_path / "memory" / "persistent.json"
    _patch_paths(monkeypatch, data_path, mirror)

    assert dm._save_persistent(str(data_path), _data()) is True

    assert data_path.exists(), "主库未写入"
    assert mirror.exists(), "镜像未写入（RS21 未修好）"
    assert mirror.read_bytes() == data_path.read_bytes(), "镜像与主库字节不一致"


def test_default_path_write_refreshes_bak(tmp_path, monkeypatch):
    """正控②：第二次写盘必须刷新 .bak（裸 open 路径不会）。"""
    data_path = tmp_path / "data" / "persistent.json"
    mirror = tmp_path / "memory" / "persistent.json"
    _patch_paths(monkeypatch, data_path, mirror)

    assert dm._save_persistent(str(data_path), _data()) is True
    first = data_path.read_bytes()

    assert dm._save_persistent(str(data_path), _data()) is True
    bak = data_path.with_suffix(".json.bak")
    assert bak.exists(), ".bak 未生成（仍是裸 open 路径）"
    assert bak.read_bytes() == first, ".bak 内容不是上一版"


def test_non_default_path_does_not_mirror(tmp_path, monkeypatch):
    """负控：显式非默认路径 ⇒ 不许产生镜像（临时/测试文件不污染 memory/）。"""
    data_path = tmp_path / "data" / "persistent.json"
    mirror = tmp_path / "memory" / "persistent.json"
    _patch_paths(monkeypatch, data_path, mirror)

    scratch = tmp_path / "scratch" / "persistent.json"
    assert dm._save_persistent(str(scratch), _data()) is True

    assert scratch.exists(), "临时文件本身应被写入"
    assert not mirror.exists(), "负控失败：临时文件写盘也去镜像了"


def test_write_failure_returns_false(tmp_path, monkeypatch):
    """错误语义（§5.5 不可裁剪）：写盘失败必须返回 False，不许静默 True。"""
    data_path = tmp_path / "data" / "persistent.json"
    mirror = tmp_path / "memory" / "persistent.json"
    _patch_paths(monkeypatch, data_path, mirror)

    # 让目标路径成为目录 ⇒ 原子写必然失败
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.mkdir()

    assert dm._save_persistent(str(data_path), _data()) is False
