"""Q9 回归：部署侧漂移第二层 —— 「源侧变了 ⇒ 部署侧本地修复被静默覆盖」。

根因（源码逐行 · 生产实测）：替换某 skill 前整目录 rmtree + copytree，
全文件无漂移检测、无备份、无出声 ⇒ 部署侧本地修复在下次同步
（gateway 启动即调）时被静默抹掉，事后不可追。

本文件把三件钉成断言（全 tmp_path，不触碰生产目录）：
- 正控：部署侧本地改过 + 源侧变了 ⇒ 出声 1 行 + 备份内容 == 被覆盖前内容
- 负控：部署侧未被改            ⇒ 零出声 + 零漂移备份目录
- 边界：部署侧改过但源侧未变    ⇒ 不重拷（无覆盖即无丢失）、不告警
"""

import json
import logging

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


def _drift_msgs(caplog):
    return [r.getMessage() for r in caplog.records if "部署侧漂移" in r.getMessage()]


def _backups(cache, name):
    root = cache.parent / "drift-backup"
    return sorted(root.glob(name + "-*")) if root.exists() else []


def test_positive_control_local_edit_backed_up_before_overwrite(env, caplog):
    """正控：部署侧被本地改过 + 源侧变了 ⇒ 出声一行 + 备份 == 改前内容 + 源侧仍权威。"""
    src, tgt, cache = env
    skills_sync.sync_skills(quiet=True)                       # 第 1 轮：建基线

    local = "alpha v1 + 部署侧本地修复"
    (tgt / "alpha" / "SKILL.md").write_text(local)
    (src / "alpha" / "SKILL.md").write_text("alpha v2 上游")
    caplog.set_level(logging.WARNING, logger="tools.skills_sync")
    caplog.clear()

    skills_sync.sync_skills(quiet=True)

    msgs = _drift_msgs(caplog)
    assert len(msgs) == 1, [r.getMessage() for r in caplog.records]
    assert "alpha" in msgs[0]
    bks = _backups(cache, "alpha")
    assert len(bks) == 1, bks
    assert (bks[0] / "SKILL.md").read_text() == local          # 备份 == 被覆盖前部署侧内容
    assert str(bks[0]) in msgs[0]                              # 出声必须含备份路径
    assert (tgt / "alpha" / "SKILL.md").read_text() == "alpha v2 上游"   # 源侧仍是权威
    assert (tgt / skills_sync.READONLY_README).exists()        # 只读政策落文


def test_negative_control_untouched_target_zero_noise(env, caplog):
    """负控：部署侧未被改 + 源侧变了 ⇒ 零出声、零漂移备份目录（连根目录都不建）。"""
    src, tgt, cache = env
    skills_sync.sync_skills(quiet=True)
    data = json.loads(cache.read_text())
    assert set(data["target"]) == {"alpha", "beta"}            # 基线已记（Q9 前提）

    (src / "beta" / "SKILL.md").write_text("beta v2 上游")
    caplog.set_level(logging.WARNING, logger="tools.skills_sync")
    caplog.clear()

    skills_sync.sync_skills(quiet=True)

    assert _drift_msgs(caplog) == []
    assert _backups(cache, "beta") == []
    assert not (cache.parent / "drift-backup").exists(), "无漂移却建了备份目录"
    assert (tgt / "beta" / "SKILL.md").read_text() == "beta v2 上游"


def test_local_edit_without_source_change_is_not_clobbered(env, caplog):
    """边界：部署侧改过但源侧未变 ⇒ 该 skill 不重拷（无覆盖即无丢失），也不告警。"""
    src, tgt, cache = env
    skills_sync.sync_skills(quiet=True)

    keep = "alpha v1 + 仅部署侧改动"
    (tgt / "alpha" / "SKILL.md").write_text(keep)
    caplog.set_level(logging.WARNING, logger="tools.skills_sync")
    caplog.clear()

    skills_sync.sync_skills(quiet=True)

    assert skills_sync.SkillSync().get_sync_status()["pending"] == 0
    assert _drift_msgs(caplog) == []
    assert (tgt / "alpha" / "SKILL.md").read_text() == keep


def test_missing_baseline_no_false_positive(env, caplog):
    """旧缓存（无部署侧基线）⇒ 不误报：首轮只建基线，不产假漂移告警/假备份。"""
    src, tgt, cache = env
    skills_sync.sync_skills(quiet=True)
    data = json.loads(cache.read_text())
    data.pop("target", None)                                   # 模拟 Q7 时代旧缓存
    cache.write_text(json.dumps(data))

    (tgt / "alpha" / "SKILL.md").write_text("alpha v1 + 本地改")
    (src / "alpha" / "SKILL.md").write_text("alpha v2 上游")
    caplog.set_level(logging.WARNING, logger="tools.skills_sync")
    caplog.clear()

    skills_sync.sync_skills(quiet=True)

    assert _drift_msgs(caplog) == []
    assert _backups(cache, "alpha") == []
    assert (tgt / "alpha" / "SKILL.md").read_text() == "alpha v2 上游"
