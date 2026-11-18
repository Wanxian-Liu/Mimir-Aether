"""B3-R1 互指注释契约测试（纯静态 + 导入级：不读写生产 ``cron/jobs.json``）。

被测对象 = ``cron/jobs.py`` 与 ``scheduler/jobs.py`` 顶部的「互指注释块」（B3-R1）。
契约三条：
  1. 两侧各写一段 A/B/C（字段语义差异 / 消费方归属 / 休眠地雷），互指命中合计 ≥2；
  2. 字段语义差异逐字登记（``next_run_at``/ISO-8601  ↔  ``next_run``/float epoch），
     且消费方名单指向真实存在的文件；
  3. 两实现共用 ``mimir_constants.get_cron_jobs_lock_path()`` 单源锁路径，且互不
     import（逻辑解耦 = 「保形不保合」可静态验证）。

设计纪律：只读源码文本 + 只在导入级取模块属性；**不调用** load_jobs/save_jobs/
mark_job_run，因此不会碰生产 jobs.json（也不创建目录）。
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CRON_PATH = REPO / "cron" / "jobs.py"
SCHED_PATH = REPO / "scheduler" / "jobs.py"

# 注释块必须在文件顶部（= 改字段的人第一眼能看到）；超出此窗口即视为未登记。
HEAD_LINES = 160

THREE_SECTIONS = ("字段语义差异", "消费方归属", "休眠地雷")


def _head(path: Path) -> str:
    """取文件前 HEAD_LINES 行文本（纯读，不 import、不执行）。"""
    assert path.is_file(), f"缺失被测文件: {path}"
    return "\n".join(path.read_text(encoding="utf-8").splitlines()[:HEAD_LINES])


@pytest.fixture(scope="module")
def heads():
    return _head(CRON_PATH), _head(SCHED_PATH)


# ---------------------------------------------------------------------------
# 1. 互指命中：双向、合计 ≥2
# ---------------------------------------------------------------------------
def test_mutual_reference_hits_at_least_two(heads):
    cron_head, sched_head = heads
    cron_to_sched = cron_head.count("scheduler/jobs.py")
    sched_to_cron = sched_head.count("cron/jobs.py")
    assert cron_to_sched >= 1, "cron/jobs.py 顶部未指向 scheduler/jobs.py"
    assert sched_to_cron >= 1, "scheduler/jobs.py 顶部未指向 cron/jobs.py"
    assert cron_to_sched + sched_to_cron >= 2, (
        f"互指命中合计 {cron_to_sched + sched_to_cron} < 2"
    )


# ---------------------------------------------------------------------------
# 2. A/B/C 三节齐备（两侧都要，缺一节 = 注释退化成闲话）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("which", ["cron", "scheduler"])
def test_three_annotation_sections_present(heads, which):
    head = heads[0] if which == "cron" else heads[1]
    missing = [s for s in THREE_SECTIONS if s not in head]
    assert not missing, f"{which}/jobs.py 顶部缺注释节: {missing}"


# ---------------------------------------------------------------------------
# 3. 字段语义差异逐字登记（同名不同义是本次的真正风险点）
# ---------------------------------------------------------------------------
def test_field_semantics_both_directions(heads):
    cron_head, sched_head = heads
    # 本侧：ISO 串键 + 明确写出对侧的 epoch 键（差异是成对出现的，不能只写一半）
    for token in ("next_run_at", "last_run_at", "ISO-8601", "next_run", "epoch"):
        assert token in cron_head, f"cron/jobs.py 注释缺字段语义标记: {token}"
    for token in ("next_run", "last_run", "epoch", "next_run_at", "ISO-8601"):
        assert token in sched_head, f"scheduler/jobs.py 注释缺字段语义标记: {token}"


# ---------------------------------------------------------------------------
# 4. 消费方归属指向真实文件（防止名单腐烂成历史传说）
# ---------------------------------------------------------------------------
def test_consumer_ownership_lists_real_files(heads):
    cron_head, sched_head = heads
    for rel in (
        "cron/__init__.py",
        "cron/scheduler.py",
        "tools/cronjob_tools.py",
        "gateway/cron_mixin.py",
        "scripts/post_restart_verify.py",
    ):
        assert rel in cron_head, f"cron/jobs.py 消费方名单缺: {rel}"
        assert (REPO / rel).is_file(), f"名单里的消费方在盘上不存在: {rel}"
    # 对侧的关键信息是「生产侧无入口」——比任何模块名都重要（决定改动的影响面）
    assert "生产侧无入口" in sched_head, "scheduler/jobs.py 未声明生产侧无入口"
    assert "cron/jobs.py" in sched_head


# ---------------------------------------------------------------------------
# 5. 休眠地雷三条（缺几条 = 下一个人会重新踩）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key", ["恒判到期", "永不触发", "自锁", "扁平 list"])
def test_dormant_landmines_recorded(heads, key):
    cron_head, sched_head = heads
    assert key in cron_head, f"cron/jobs.py 休眠地雷缺标记: {key}"
    assert key in sched_head, f"scheduler/jobs.py 休眠地雷缺标记: {key}"


# ---------------------------------------------------------------------------
# 6. 锁路径单源：两实现必须解析到同一个旁车锁文件（跨实现互斥的物理前提）
# ---------------------------------------------------------------------------
def test_single_source_lock_path_is_shared():
    from mimir_constants import get_cron_jobs_lock_path

    cron_jobs = importlib.import_module("cron.jobs")
    sched_jobs = importlib.import_module("scheduler.jobs")

    expected = get_cron_jobs_lock_path()
    assert cron_jobs._WRITE_LOCK_FILE == expected
    assert sched_jobs._WRITE_LOCK_FILE == expected
    assert cron_jobs._WRITE_LOCK_FILE == sched_jobs._WRITE_LOCK_FILE


# ---------------------------------------------------------------------------
# 7. 「保形不保合」静态证据：两实现互不 import + 各自 write_window 可用
# ---------------------------------------------------------------------------
def test_implementations_stay_decoupled():
    cron_src = CRON_PATH.read_text(encoding="utf-8")
    sched_src = SCHED_PATH.read_text(encoding="utf-8")

    assert "scheduler.jobs" not in cron_src.replace("scheduler/jobs.py", ""), (
        "cron/jobs.py 出现了对 scheduler.jobs 的代码级引用（应只作注释互指）"
    )
    assert "from scheduler" not in cron_src
    assert "import scheduler" not in cron_src.replace("# ", "")
    assert "cron.jobs" not in sched_src.replace("cron/jobs.py", ""), (
        "scheduler/jobs.py 出现了对 cron.jobs 的代码级引用（应只作注释互指）"
    )

    assert callable(importlib.import_module("cron.jobs").write_window)
    assert callable(importlib.import_module("scheduler.jobs").write_window)


# ---------------------------------------------------------------------------
# 8. 同一目标文件、不同 schema：路径相同才算「互指」成立
# ---------------------------------------------------------------------------
def test_same_target_file_different_schema():
    cron_jobs = importlib.import_module("cron.jobs")
    sched_jobs = importlib.import_module("scheduler.jobs")

    assert cron_jobs.JOBS_FILE == sched_jobs.JOBS_FILE
    assert Path(cron_jobs.JOBS_FILE).name == "jobs.json"
    # 导入级检查：契约成立与否只看模块属性，不触发任何读写
    assert hasattr(cron_jobs, "load_jobs") and hasattr(cron_jobs, "save_jobs")
    assert hasattr(sched_jobs, "load_jobs") and hasattr(sched_jobs, "save_jobs")


# ---------------------------------------------------------------------------
# 9. 消费方名单 = 全仓实际 import 面的超集（自审席补充 2026-11-18）
#    —— 防「名单腐烂成历史传说」：注释写谁，就必须覆盖 grep 得到的真实读者。
#    负控逻辑：探针用「假想文件名」断言不可命中，证明正则确有鉴别力（不是恒真）。
# ---------------------------------------------------------------------------
_SKIP_PREFIX = (
    "tests/", ".worktrees/", "checkpoints/", ".venv", "node_modules/", "data/", "backups/",
)
_CRON_IMPORT = re.compile(
    r"^\s*(?:from\s+cron\.jobs\s+import|from\s+cron\s+import\s+jobs\b|import\s+cron\.jobs)", re.M
)
_SCHED_IMPORT = re.compile(
    r"^\s*(?:from\s+scheduler\.jobs\s+import|from\s+scheduler\s+import\s+jobs\b"
    r"|import\s+scheduler\.jobs)", re.M
)
_REL_JOBS_IMPORT = re.compile(r"^\s*from\s+\.jobs\s+import", re.M)


def _importers(pattern: re.Pattern, skip_self: str) -> set[str]:
    found: set[str] = set()
    for py in REPO.rglob("*.py"):
        rel = py.relative_to(REPO).as_posix()
        if rel.startswith(_SKIP_PREFIX) or rel == skip_self:
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pattern.search(text):
            found.add(rel)
    return found


def test_consumer_lists_cover_actual_importers(heads):
    cron_head, sched_head = heads

    cron_actual = _importers(_CRON_IMPORT, "cron/jobs.py")
    assert cron_actual, "探针失效：全仓一个 cron.jobs 读者都没搜到（搜索面问题，不是零读者）"
    assert "no/such/consumer.py" not in cron_actual  # 负控：探针非恒真
    missing = sorted(r for r in cron_actual if r not in cron_head)
    assert not missing, f"cron/jobs.py 消费方名单未覆盖实际读者: {missing}"

    sched_actual = _importers(_SCHED_IMPORT, "scheduler/jobs.py")
    rel_actual = {
        rel for rel in (
            py.relative_to(REPO).as_posix()
            for py in (REPO / "scheduler").rglob("*.py")
            if py.relative_to(REPO).as_posix() != "scheduler/jobs.py"
            and _REL_JOBS_IMPORT.search(py.read_text(encoding="utf-8", errors="ignore"))
        )
    }
    sched_actual |= rel_actual
    missing_s = sorted(r for r in sched_actual if r not in sched_head)
    assert not missing_s, f"scheduler/jobs.py 消费方名单未覆盖实际读者: {missing_s}"
    assert "scheduler/scheduler.py" in sched_actual, "探针失效：相对导入读者未被捕获"
