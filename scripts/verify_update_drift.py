#!/usr/bin/env python3
"""Q11 部署侧漂移闸 · 两向判据（正控 / 负控 / 噪声 / 边界）—— 全临时目录，零生产写入。

跑法（cwd = 仓根）:
  /home/rayliu/src/MimirAether/.venv/bin/python3 scripts/verify_update_drift.py
输出：每项判据一行 `KEY=value`；末行 `failed_checks=N`；rc=0 表示全过。

- 正控：部署侧被本地改过 ⇒ 覆盖前必须
  ①上报 drift 含该目录 ②出声 1 行 ③备份目录存在
  ④备份内容 == 被覆盖前部署侧内容 ⑤部署侧最终内容 == 源侧内容（源侧权威）
  ⑥部署根有只读政策文件
- 负控：部署侧未被改 ⇒ 零出声、零新增备份、内容照常覆盖
- 噪声：部署侧只多出 __pycache__ ⇒ 不算漂移（否则闸恒响 = 无闸）
- 边界：旧部署（有内容无基线）⇒ 不误报（首轮只建基线）
"""

import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mimir_cli import update_command as uc  # noqa: E402

#: 判据期望值（不在表内的 key 只作信息展示，不计入 failed_checks）
EXPECT = {
    "pos_drift_reported": 1,
    "pos_warn_lines": 1,
    "pos_backup_dirs": 1,
    "pos_backup_is_pre_overwrite": 1,
    "pos_deployed_equals_source": 1,
    "pos_readonly_notice": 1,
    "neg_drift_empty": 1,
    "neg_warn_lines": 0,
    "neg_new_backup_dirs": 0,
    "neg_deployed_equals_source": 1,
    "noise_drift_empty": 1,
    "noise_warn_lines": 0,
    "edge_no_baseline_drift_empty": 1,
    "edge_warn_lines": 0,
}


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


def _mk(root, name, text):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "mod.py").write_text(text, encoding="utf-8")


def _backups(cache):
    root = cache.parent / "drift-backup"
    return sorted(p for p in root.glob("*") if p.is_dir()) if root.exists() else []


def _drifts(records, mark):
    return [m for m in records[mark:] if "部署侧漂移" in m]


def main() -> int:
    res = {}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        extracted = tmp / "extracted"
        deploy = tmp / "deploy"
        cache = tmp / "cache" / "update_sync_baseline.json"
        deploy.mkdir(parents=True)
        for name, text in (("alpha", "alpha v1"), ("beta", "beta v1")):
            _mk(extracted, name, text)

        # 基线路径重定向到临时目录（不碰生产缓存 / 生产目录）
        uc._update_drift_cache_path = lambda: cache

        cap = _Capture()
        logging.getLogger("mimir_cli.update_command").addHandler(cap)

        # 第 1 轮：建基线（此刻部署侧 == 源侧）
        uc._apply_zip_overwrite(str(extracted), deploy)
        mark = len(cap.records)

        # ---------- 正控：部署侧被本地改过 ----------
        local_edit = "alpha v1 + 部署侧本地修复（会被覆盖，须先备份）"
        (deploy / "alpha" / "mod.py").write_text(local_edit, encoding="utf-8")
        _, drift = uc._apply_zip_overwrite(str(extracted), deploy)
        warns = _drifts(cap.records, mark)
        bks = [b for b in _backups(cache) if b.name.startswith("alpha-")]
        bk_file = (bks[0] / "mod.py") if bks else None
        res["pos_drift_reported"] = int(drift == ["alpha"])
        res["pos_warn_lines"] = len(warns)
        res["pos_backup_dirs"] = len(bks)
        res["pos_backup_is_pre_overwrite"] = int(
            bool(bk_file) and bk_file.read_text(encoding="utf-8") == local_edit
        )
        res["pos_deployed_equals_source"] = int(
            (deploy / "alpha" / "mod.py").read_text(encoding="utf-8") == "alpha v1"
        )
        res["pos_readonly_notice"] = int((deploy / uc.UPDATE_READONLY_README).exists())
        res["pos_backup_path"] = bks[0] if bks else "-"

        # ---------- 负控：部署侧未被改 ----------
        mark = len(cap.records)
        nb_before = len(_backups(cache))
        _, drift2 = uc._apply_zip_overwrite(str(extracted), deploy)
        res["neg_drift_empty"] = int(drift2 == [])
        res["neg_warn_lines"] = len(_drifts(cap.records, mark))
        res["neg_new_backup_dirs"] = len(_backups(cache)) - nb_before
        res["neg_deployed_equals_source"] = int(
            (deploy / "beta" / "mod.py").read_text(encoding="utf-8") == "beta v1"
        )

        # ---------- 噪声：只多出 __pycache__ ----------
        mark = len(cap.records)
        pyc = deploy / "beta" / "__pycache__"
        pyc.mkdir()
        (pyc / "mod.cpython-312.pyc").write_bytes(b"\x00volatile")
        _, drift3 = uc._apply_zip_overwrite(str(extracted), deploy)
        res["noise_drift_empty"] = int(drift3 == [])
        res["noise_warn_lines"] = len(_drifts(cap.records, mark))

        # ---------- 边界：旧部署（有内容，无基线）----------
        fresh = tmp / "fresh-deploy"
        (fresh / "alpha").mkdir(parents=True)
        (fresh / "alpha" / "mod.py").write_text("alpha v1 + 本地改", encoding="utf-8")
        cache.unlink()                      # 抹掉基线，模拟旧部署首轮
        mark = len(cap.records)
        _, drift4 = uc._apply_zip_overwrite(str(extracted), fresh)
        res["edge_no_baseline_drift_empty"] = int(drift4 == [])
        res["edge_warn_lines"] = len(_drifts(cap.records, mark))

    bad = []
    for key, want in EXPECT.items():
        got = res.get(key)
        got = got if isinstance(got, int) else int(got)
        status = "ok" if got == want else "FAIL"
        if got != want:
            bad.append("%s=%s (want %s)" % (key, got, want))
        print("%s=%s  [%s]" % (key, got, status))
    print("pos_backup_path=%s" % res.get("pos_backup_path"))
    print("failed_checks=%d" % len(bad))
    for b in bad:
        print("FAIL " + b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
