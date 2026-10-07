"""Q7 回归：skills_sync 闸门判据（正控 / 负控 / 旧形态兼容 / 目标缺失）。

根因（生产实测）：旧口径 ``pending = len(源侧当前存量) - len(缓存历史名单)``
= 两套不同语义集合相减 ⇒ 19 - 29 = **-10** ⇒ ``pending == 0`` 恒 False
⇒ ``skills_sync.py:179`` 的「跳过未变」闸**从未生效** ⇒ 每次 gateway 启动
整类目 ``rmtree`` + ``copytree`` 全量重拷（部署侧本地修复被覆盖）。

本文件把「正控（真无变化 ⇒ 零重拷）」与「负控（改一个源文件 ⇒ 只同步它）」
都钉成断言；用 monkeypatch 把源/目标/缓存三路径重定向到 tmp_path，
不触碰生产目录。
"""

import json
import shutil
from pathlib import Path

import pytest

from tools import skills_sync


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """tmp 源目录（alpha/beta）+ tmp 目标目录 + tmp 缓存路径。"""
    src = tmp_path / "src"
    tgt = tmp_path / "tgt"
    cache = tmp_path / "cache" / "skills_sync.json"
    cache.parent.mkdir(parents=True)
    for name, text in (("alpha", "alpha v1"), ("beta", "beta v1")):
        d = src / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(text)
    monkeypatch.setattr(skills_sync, "get_skills_source_dir", lambda: src)
    monkeypatch.setattr(skills_sync, "get_skills_target_dir", lambda: tgt)
    monkeypatch.setattr(skills_sync, "get_sync_cache_path", lambda: cache)
    return src, tgt, cache


def _spy_copytree(monkeypatch):
    """记下每次真的调用了 copytree 的 skill 名（= 「重拷」的机器证据）。"""
    calls = []
    real = skills_sync.shutil.copytree

    def spy(s, d, *a, **k):
        calls.append(Path(s).name)
        return real(s, d, *a, **k)

    monkeypatch.setattr(skills_sync.shutil, "copytree", spy)
    return calls


def _file_marks(root: Path):
    return {
        str(p.relative_to(root)): p.stat().st_mtime_ns
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_legacy_list_cache_never_negative_pending(env):
    """根因回归：旧 list 形态缓存（含已删技能名）⇒ pending 必须 = 源侧数，不得为负。"""
    src, tgt, cache = env
    cache.write_text(json.dumps({"synced": ["alpha", "beta"] + ["ghost%d" % i for i in range(27)]}))

    st = skills_sync.SkillSync().get_sync_status()   # 只调一次（见上）

    assert st["total"] == 2
    assert st["pending"] == 2          # 旧算法: 2 - 29 = -27（生产同型: 19 - 29 = -10）
    assert st["synced"] == 0
    assert st["cached_total"] == 0     # 旧 list 形态无摘要 ⇒ 视为「无缓存」全部待同步一次

def test_positive_control_unchanged_second_run_zero_recopy(env, monkeypatch):
    """正控：首轮全量；源侧无变化时第二轮 pending==0 且**零次** copytree、文件 mtime 不变。"""
    src, tgt, cache = env
    calls = _spy_copytree(monkeypatch)

    skills_sync.sync_skills(quiet=True)
    assert sorted(calls) == ["alpha", "beta"], calls
    marks_before = _file_marks(tgt)
    assert marks_before, "首轮没产出任何目标文件"
    calls.clear()

    skills_sync.sync_skills(quiet=True)          # 第二次启动等价动作

    st = skills_sync.SkillSync().get_sync_status()
    assert st["pending"] == 0, st
    assert calls == [], "真无变化却仍在重拷: %s" % calls
    assert _file_marks(tgt) == marks_before, "目标文件 mtime 变了 ⇒ 发生过重拷"


def test_negative_control_only_changed_skill_recopied(env, monkeypatch):
    """负控：故意改一个源文件 ⇒ 只同步它（未变的不动，mtime 为证）。"""
    src, tgt, cache = env
    calls = _spy_copytree(monkeypatch)

    skills_sync.sync_skills(quiet=True)
    calls.clear()
    alpha_before = _file_marks(tgt / "alpha")
    (src / "beta" / "SKILL.md").write_text("beta v2 -- 只改这一个源文件")

    skills_sync.sync_skills(quiet=True)

    assert calls == ["beta"], "应只同步 beta，实际: %s" % calls
    assert (tgt / "beta" / "SKILL.md").read_text() == "beta v2 -- 只改这一个源文件"
    assert _file_marks(tgt / "alpha") == alpha_before, "未变的 alpha 被动了"


def test_missing_target_resyncs(env, monkeypatch):
    """目标缺失（被删）⇒ 必须补同步（不能因缓存命中而漏拷）。"""
    src, tgt, cache = env
    calls = _spy_copytree(monkeypatch)

    skills_sync.sync_skills(quiet=True)
    shutil.rmtree(tgt / "alpha")
    calls.clear()

    skills_sync.sync_skills(quiet=True)

    assert calls == ["alpha"], "目标缺失未补同步: %s" % calls
    assert (tgt / "alpha" / "SKILL.md").read_text() == "alpha v1"


def test_cache_upgraded_to_digest_map_and_idempotent(env, monkeypatch):
    """缓存形态升级：同步后为 {name: sha256}；再次运行 pending==0（自愈且幂等）。"""
    src, tgt, cache = env
    skills_sync.sync_skills(quiet=True)

    data = json.loads(cache.read_text())

    assert isinstance(data["synced"], dict), data
    assert set(data["synced"]) == {"alpha", "beta"}, data
    assert all(len(v) == 64 for v in data["synced"].values()), data
    assert skills_sync.SkillSync().get_sync_status()["pending"] == 0


def test_decision_recorded_in_cache(env, monkeypatch):
    """可观测性：判决落痕 —— 首轮 action=sync/pending=N，次轮 action=skip/pending=0。"""
    src, tgt, cache = env

    skills_sync.sync_skills(quiet=True)
    d1 = json.loads(cache.read_text())["last_decision"]
    assert d1["action"] == "sync" and d1["pending"] == 2, d1

    skills_sync.sync_skills(quiet=True)
    d2 = json.loads(cache.read_text())["last_decision"]
    assert d2["action"] == "skip" and d2["pending"] == 0 and d2["pending_skills"] == [], d2
