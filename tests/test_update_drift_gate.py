"""Q11 回归：`mimir update` 静默覆盖 —— 部署侧本地改动被无检测抹掉。

根因（源码逐行 · 生产实测）：``mimir_cli/update_command.py::_update_via_zip``
对 skills/ scripts/ config/ 等顶层目录整目录 rmtree + copytree，
全文件无漂移检测、无备份、无声 ⇒ 部署侧本地修复在下次更新时被静默抹掉，
事后不可追（与 Q9 ``tools/skills_sync.py`` 同族）。

本文件把五件钉成断言（全 tmp_path，不触碰生产目录）：
- 正控：部署侧本地改过 ⇒ 出声 1 行 + 备份内容 == 被覆盖前内容 + 源侧仍权威
- 负控：部署侧未被改    ⇒ 零出声 + 零漂移备份目录（连根目录都不建）
- 边界：旧部署（无基线）⇒ 不误报（首轮只建基线，防假阳性）
- 噪声：部署侧只多出 __pycache__ ⇒ 不算漂移（否则闸恒响 = 无闸）
- 契约：preserve 集合与 item 计数不变（负控「行为不变」的另一半）
"""

import json
import logging

import pytest

from mimir_cli import update_command as uc

_LOGGER = "mimir_cli.update_command"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """tmp 源目录（alpha/beta）+ tmp 部署根 + tmp 基线缓存路径。"""
    extracted = tmp_path / "extracted"
    deploy = tmp_path / "deploy"
    cache = tmp_path / "cache" / "update_sync_baseline.json"
    for name, text in (("alpha", "alpha v1"), ("beta", "beta v1")):
        d = extracted / name
        d.mkdir(parents=True)
        (d / "mod.py").write_text(text)
    deploy.mkdir(parents=True)
    monkeypatch.setattr(uc, "_update_drift_cache_path", lambda: cache)
    return extracted, deploy, cache


def _drift_msgs(caplog):
    return [r.getMessage() for r in caplog.records if "部署侧漂移" in r.getMessage()]


def _backups(cache, name):
    root = cache.parent / "drift-backup"
    return sorted(root.glob(name + "-*")) if root.exists() else []


def test_positive_control_local_edit_backed_up_before_overwrite(env, caplog):
    """正控：部署侧被本地改过 ⇒ 出声一行 + 备份 == 改前内容 + 源侧仍权威。"""
    extracted, deploy, cache = env
    uc._apply_zip_overwrite(str(extracted), deploy)          # 第 1 轮：建基线

    local = "alpha v1 + 部署侧本地修复"
    (deploy / "alpha" / "mod.py").write_text(local)
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    caplog.clear()

    count, drift = uc._apply_zip_overwrite(str(extracted), deploy)

    assert drift == ["alpha"], drift
    msgs = _drift_msgs(caplog)
    assert len(msgs) == 1, [r.getMessage() for r in caplog.records]
    assert "alpha" in msgs[0]
    bks = _backups(cache, "alpha")
    assert len(bks) == 1, bks
    assert (bks[0] / "mod.py").read_text() == local          # 备份 == 被覆盖前内容
    assert str(bks[0]) in msgs[0]                            # 出声必须含备份路径
    assert (deploy / "alpha" / "mod.py").read_text() == "alpha v1"   # 源侧仍权威
    assert (deploy / uc.UPDATE_READONLY_README).exists()     # 只读政策落文


def test_negative_control_untouched_target_zero_noise(env, caplog):
    """负控：部署侧未被改 ⇒ 零出声、零漂移备份目录、内容照常覆盖（行为不变）。"""
    extracted, deploy, cache = env
    uc._apply_zip_overwrite(str(extracted), deploy)
    data = json.loads(cache.read_text())
    assert set(data["target"]) == {"alpha", "beta"}          # 基线已记（Q11 前提）

    caplog.set_level(logging.WARNING, logger=_LOGGER)
    caplog.clear()

    count, drift = uc._apply_zip_overwrite(str(extracted), deploy)

    assert drift == []
    assert _drift_msgs(caplog) == []
    assert _backups(cache, "alpha") == []
    assert not (cache.parent / "drift-backup").exists(), "无漂移却建了备份目录"
    assert (deploy / "alpha" / "mod.py").read_text() == "alpha v1"


def test_missing_baseline_no_false_positive(env, caplog):
    """边界：旧部署（有内容、无基线）⇒ 不误报：首轮只建基线，不产假告警/假备份。"""
    extracted, deploy, cache = env
    (deploy / "alpha").mkdir(parents=True)
    (deploy / "alpha" / "mod.py").write_text("alpha v1 + 本地改")
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    caplog.clear()

    count, drift = uc._apply_zip_overwrite(str(extracted), deploy)

    assert drift == []
    assert _drift_msgs(caplog) == []
    assert _backups(cache, "alpha") == []
    assert (deploy / "alpha" / "mod.py").read_text() == "alpha v1"


def test_pycache_noise_does_not_trigger_drift(env, caplog):
    """噪声：部署侧只多出 __pycache__ ⇒ 不算漂移（恒响的闸 = 无闸）。"""
    extracted, deploy, cache = env
    uc._apply_zip_overwrite(str(extracted), deploy)

    pyc = deploy / "alpha" / "__pycache__"
    pyc.mkdir()
    (pyc / "mod.cpython-311.pyc").write_bytes(b"\x00volatile")
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    caplog.clear()

    count, drift = uc._apply_zip_overwrite(str(extracted), deploy)

    assert drift == [], "易变产物 __pycache__ 被计入摘要 ⇒ 闸恒响 = 无闸"
    assert _drift_msgs(caplog) == []


def test_preserve_contract_and_item_count(env):
    """契约：preserve 集合仍被跳过、item 计数仍只数被覆盖的顶层项。"""
    extracted, deploy, cache = env
    for name in ("venv", "node_modules", ".git"):
        d = extracted / name
        d.mkdir()
        (d / "keep.txt").write_text("x")
    count, drift = uc._apply_zip_overwrite(str(extracted), deploy)
    assert count == 2, count                 # 只 alpha + beta
    assert not (deploy / "venv").exists()
    assert not (deploy / "node_modules").exists()
    assert not (deploy / ".git").exists()
