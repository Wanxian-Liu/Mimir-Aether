#!/usr/bin/env python3
"""Q9 部署侧漂移闸 · 两向判据（正控 / 负控）—— 全临时目录，零生产写入。

跑法（cwd = 仓根）:  python3 scripts/verify_skills_sync_drift.py
输出：每项判据一行 `KEY=value`；末行 `rc=0` 表示两向都过。

- 正控：部署侧被本地改过 **且** 源侧变了 ⇒ 同步必须
  ①出声 1 行 ②备份目录存在 ③备份内容 == 被覆盖前部署侧内容
  ④部署侧最终内容 == 源侧内容（源侧权威）⑤部署侧根有只读政策文件
- 负控：部署侧未被改 **且** 源侧变了 ⇒ 零出声、零漂移备份目录
- 边界：部署侧被改但源侧未变 ⇒ 该 skill 不重拷（无覆盖 = 无丢失），不告警
"""

import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import skills_sync  # noqa: E402


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


def _mk(root, name, text):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")


def _backups(cache):
    root = cache.parent / "drift-backup"
    return sorted(root.glob("*")) if root.exists() else []


def main() -> int:
    lines = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        src = tmp / "src"
        tgt = tmp / "tgt"
        cache = tmp / "cache" / "skills_sync.json"
        cache.parent.mkdir(parents=True)
        _mk(src, "alpha", "alpha v1")
        _mk(src, "beta", "beta v1")

        # 三路径全部重定向到临时目录（不碰生产目录 / 生产缓存）
        skills_sync.get_skills_source_dir = lambda: src
        skills_sync.get_skills_target_dir = lambda: tgt
        skills_sync.get_sync_cache_path = lambda: cache

        cap = _Capture()
        logging.getLogger("tools.skills_sync").addHandler(cap)

        # 第 1 轮：建基线（此刻部署侧 == 源侧）
        skills_sync.sync_skills(quiet=True)
        base = len(cap.records)

        # ---------- 正控：部署侧本地改过 + 源侧变了 ----------
        local_edit = "alpha v1 + 部署侧本地修复（会被覆盖，须先备份）"
        (tgt / "alpha" / "SKILL.md").write_text(local_edit, encoding="utf-8")
        (src / "alpha" / "SKILL.md").write_text("alpha v2 上游", encoding="utf-8")
        skills_sync.sync_skills(quiet=True)
        pos_warns = [m for m in cap.records[base:] if "部署侧漂移" in m and "alpha" in m]
        bks = [b for b in _backups(cache) if b.name.startswith("alpha-")]
        bk_file = (bks[0] / "SKILL.md") if bks else None
        lines += [
            "pos_warn_lines=%d" % len(pos_warns),
            "pos_backup_dirs=%d" % len(bks),
            "pos_backup_is_pre_overwrite=%d"
            % int(bool(bk_file) and bk_file.read_text(encoding="utf-8") == local_edit),
            "pos_deployed_equals_source=%d"
            % int((tgt / "alpha" / "SKILL.md").read_text(encoding="utf-8") == "alpha v2 上游"),
            "pos_readonly_notice=%d" % int((tgt / skills_sync.READONLY_README).exists()),
            "pos_backup_path=%s" % (bks[0] if bks else "-"),
        ]

        # ---------- 负控：部署侧未被改 + 源侧变了 ----------
        mark = len(cap.records)
        (src / "beta" / "SKILL.md").write_text("beta v2 上游", encoding="utf-8")
        skills_sync.sync_skills(quiet=True)
        neg_warns = [m for m in cap.records[mark:] if "部署侧漂移" in m]
        lines += [
            "neg_warn_lines=%d" % len(neg_warns),
            "neg_backup_dirs=%d" % len([b for b in _backups(cache) if b.name.startswith("beta-")]),
            "neg_deployed_equals_source=%d"
            % int((tgt / "beta" / "SKILL.md").read_text(encoding="utf-8") == "beta v2 上游"),
        ]

        # ---------- 边界：部署侧被改但源侧未变 ----------
        mark = len(cap.records)
        keep = "beta v2 上游 + 仅部署侧改动（源侧未变 ⇒ 本轮不重拷）"
        (tgt / "beta" / "SKILL.md").write_text(keep, encoding="utf-8")
        skills_sync.sync_skills(quiet=True)
        lines += [
            "edge_warn_lines=%d" % len([m for m in cap.records[mark:] if "部署侧漂移" in m]),
            "edge_local_edit_survives=%d"
            % int((tgt / "beta" / "SKILL.md").read_text(encoding="utf-8") == keep),
        ]

    bad = [
        ln for ln in lines
        if ln.startswith("pos_") and ln.endswith("=0")
        or ln.startswith("neg_warn") and not ln.endswith("=0")
        or ln.startswith("neg_backup_dirs") and not ln.endswith("=0")
        or ln.startswith("neg_deployed_equals_source") and ln.endswith("=0")
        or ln.startswith("edge_warn_lines") and not ln.endswith("=0")
        or ln.startswith("edge_local_edit_survives") and ln.endswith("=0")
    ]
    for ln in lines:
        print(ln)
    print("failed_checks=%d" % len(bad))
    for ln in bad:
        print("FAIL " + ln)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
