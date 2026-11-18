"""T91 / B3-R1~R4 写路径四连修回归（2026-11-18 全面审计 C 节）。

四臂崩溃注入（负控：monkeypatch 写盘原语制造中途崩溃 ⇒ 旧数据必须原地
完好）+ 损坏隔离留盘 + 跨进程并发写不丢更新。

判据必须能红：旧实现（write_text 直写 / 无锁 / 裸 except→[]）在本文件各臂
同款注入下会毁数据 —— 2026-11-18 已对修复前备份（scratch/t91-backup-*）
实测复现红（torn-write→load([])→mark 回写 = 全部任务清零；并发 2×30 丢
写入），见 T91 交付回执。

隔离契约：不碰生产 ``~/.mimiraether`` —— 全部路径经 fixture 重定向 tmp。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cron_home(tmp_path, monkeypatch):
    """把两套实现（cron/jobs.py + scheduler/jobs.py）指到同一 tmp 运行时家。

    两模块共享同一 JOBS_FILE 与同一把旁车锁（与生产布局一致），只是根在 tmp。
    """
    home = tmp_path / "mimir_home"
    (home / "cron").mkdir(parents=True)
    (home / "data").mkdir(parents=True)
    jobs_file = home / "cron" / "jobs.json"
    lock_file = home / "data" / "cron_jobs.write.lock"

    import cron.jobs as cj
    import scheduler.jobs as sj

    monkeypatch.setattr(cj, "JOBS_FILE", jobs_file)
    monkeypatch.setattr(cj, "_WRITE_LOCK_FILE", lock_file)
    monkeypatch.setattr(sj, "JOBS_FILE", jobs_file)
    monkeypatch.setattr(sj, "_WRITE_LOCK_FILE", lock_file)
    return home


def _raise_boom(*_a, **_k):
    raise RuntimeError("injected crash mid-write (T91 negative control)")


# ===========================================================================
# 臂1 · cron/jobs.py：save 原子写中途崩 ⇒ 旧数据原地完好
# ===========================================================================

def test_arm1_cron_save_crash_keeps_old_data(cron_home, monkeypatch):
    import cron.jobs as cj

    cj.save_jobs([{"id": "old-1", "name": "旧数据"}])
    before = cj.JOBS_FILE.read_text(encoding="utf-8")

    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", _raise_boom)  # tmp 已写、replace 未达 ⇒ 崩
    with pytest.raises(RuntimeError):
        cj.save_jobs([{"id": "new", "name": "崩溃写"}])
    monkeypatch.setattr(os, "fsync", real_fsync)  # 只还原注入原语，不动 fixture 补丁

    # 旧数据原地完好（一个字节都不动）
    assert cj.JOBS_FILE.read_text(encoding="utf-8") == before
    # tmp 残骸已清，不留给下次 load 撞上
    assert not list(cj.JOBS_FILE.parent.glob(".*.tmp.*"))
    # 注入后写路径仍健康（锁窗口未坏）
    cj.save_jobs([{"id": "new", "name": "崩溃写"}])
    assert [j["id"] for j in cj.load_jobs()] == ["new"]


# ===========================================================================
# 臂2 · scheduler/jobs.py：同族注入 ⇒ 同样断言
# ===========================================================================

def test_arm2_scheduler_save_crash_keeps_old_data(cron_home, monkeypatch):
    import scheduler.jobs as sj

    sj.save_jobs([{"id": "old-1", "name": "旧数据"}])
    before = sj.JOBS_FILE.read_text(encoding="utf-8")

    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", _raise_boom)
    with pytest.raises(RuntimeError):
        sj.save_jobs([{"id": "new"}])
    monkeypatch.setattr(os, "fsync", real_fsync)

    assert sj.JOBS_FILE.read_text(encoding="utf-8") == before
    assert not list(sj.JOBS_FILE.parent.glob(".*.tmp.*"))
    sj.save_jobs([{"id": "new"}])
    assert [j["id"] for j in sj.load_jobs()] == ["new"]


# ===========================================================================
# 臂3 · learn_and_evolve_8h.py：append 中途崩 ⇒ 旧日志原地完好
# ===========================================================================

def test_arm3_evolution_append_crash_keeps_log(cron_home, monkeypatch):
    import scheduler.tasks.learn_and_evolve_8h as le

    log = cron_home / "learnings" / "evolution_log_8h.json"
    log.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(le, "EVOLUTION_LOG", log)

    le.save_evolution_log("topic-1", "success", "x.py")
    before = log.read_text(encoding="utf-8")

    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", _raise_boom)
    with pytest.raises(RuntimeError):
        le.save_evolution_log("topic-2", "failed", "y.py")
    monkeypatch.setattr(os, "fsync", real_fsync)

    # append-only 的负控语义：崩在中途 ⇒ **旧字节必须分毫不差地保留在头部**
    # （新行可能已/未落盘，但历史行永不改写——旧实现全量回写则旧档可被撕裂）
    after = log.read_text(encoding="utf-8")
    assert after.startswith(before)
    complete = [ln for ln in after.splitlines() if ln.strip()]
    for ln in complete:
        json.loads(ln)  # 无撕裂行
    # append-only：写路径不读旧档 ⇒ 历史行只增不改
    le.save_evolution_log("topic-2", "failed", "y.py")
    rows = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
    assert [r["topic"] for r in rows] == ["topic-1", "topic-2", "topic-2"]


def test_evolution_legacy_array_migrated_losslessly(cron_home, monkeypatch):
    """遗留 JSON 数组档：写前锁内一次性无损迁移为 JSONL（字节不灭）。"""
    import scheduler.tasks.learn_and_evolve_8h as le

    log = cron_home / "learnings" / "evolution_log_8h.json"
    log.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(le, "EVOLUTION_LOG", log)
    legacy = [
        {"timestamp": "2026-11-01T00:00:00", "topic": "old-1", "status": "success",
         "hermes_file": "a.py"},
        {"timestamp": "2026-11-02T00:00:00", "topic": "old-2", "status": "failed",
         "hermes_file": "b.py"},
    ]
    log.write_text(json.dumps(legacy, indent=2, ensure_ascii=False), encoding="utf-8")

    le.save_evolution_log("new-1", "success", "c.py")

    rows = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
    assert [r["topic"] for r in rows] == ["old-1", "old-2", "new-1"]
    assert rows[0] == legacy[0] and rows[1] == legacy[1]  # 无损
    assert not list(log.parent.glob("*corrupt-*"))


def test_evolution_garbage_file_quarantined_not_appended_into(cron_home, monkeypatch):
    """垃圾件（非数组非 JSONL）：隔离改名留盘，新记录落干净新档，不埋进垃圾。"""
    import scheduler.tasks.learn_and_evolve_8h as le

    log = cron_home / "learnings" / "evolution_log_8h.json"
    log.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(le, "EVOLUTION_LOG", log)
    log.write_text("GARBAGE-NOT-JSON", encoding="utf-8")

    le.save_evolution_log("fresh", "success", "w.py")

    quarantined = list(log.parent.glob("evolution_log_8h.json.corrupt-*"))
    assert len(quarantined) == 1
    assert quarantined[0].read_text(encoding="utf-8") == "GARBAGE-NOT-JSON"  # 字节留盘
    rows = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
    assert [r["topic"] for r in rows] == ["fresh"]  # 新档干净，未混入垃圾


# ===========================================================================
# 臂4 · 损坏隔离：改名 .corrupt-<ts> 留盘，字节不灭；OSError 出声
# ===========================================================================

def test_arm4_corrupt_file_quarantined_bytes_preserved(cron_home):
    import cron.jobs as cj
    import scheduler.jobs as sj

    garbage = '{"jobs": [ TRUNC-BY-TEARED-LEGACY-WRITE'
    cj.JOBS_FILE.write_text(garbage, encoding="utf-8")
    assert cj.load_jobs() == []  # 损坏≠有任务，但……
    quarantined = list(cj.JOBS_FILE.parent.glob("jobs.json.corrupt-*"))
    assert len(quarantined) == 1
    # ……旧字节一个不灭地留在隔离区
    assert quarantined[0].read_text(encoding="utf-8") == garbage
    assert not cj.JOBS_FILE.exists()  # 在位件已改名，不再半份挂着

    # 第二套实现同款行为
    sj.JOBS_FILE.write_text("not json at all{{{", encoding="utf-8")
    assert sj.load_jobs() == []
    assert len(list(sj.JOBS_FILE.parent.glob("jobs.json.corrupt-*"))) == 2

    # 隔离后下一次保存从 [] 重建 —— 「损坏+标记=清零」链已断
    cj.save_jobs([{"id": "reborn"}])
    assert [j["id"] for j in cj.load_jobs()] == ["reborn"]


def test_load_oserror_is_loud_not_silent_empty(cron_home):
    """存储不可用（OSError）必须出声上抛，不许静默当空（审计 C 修法4）。"""
    import cron.jobs as cj
    import scheduler.jobs as sj

    cj.JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if cj.JOBS_FILE.exists():
        cj.JOBS_FILE.unlink()
    cj.JOBS_FILE.mkdir()  # 目录 ⇒ read_text 抛 IsADirectoryError(OSError)
    with pytest.raises(OSError):
        cj.load_jobs()
    with pytest.raises(OSError):
        sj.load_jobs()


# ===========================================================================
# 并发（真实跨进程）：同写 jobs.json 不丢更新
# ===========================================================================

_CHILD = textwrap.dedent(
    """
    import sys, json, time
    sys.path.insert(0, sys.argv[3])
    tag, n, ready, go = sys.argv[1], int(sys.argv[2]), sys.argv[4], sys.argv[5]
    from cron.jobs import create_job, list_jobs
    with open(ready, "w") as f:
        f.write("ok")
    while not __import__("os").path.exists(go):
        time.sleep(0.01)
    for i in range(n):
        create_job(prompt=f"prompt-{tag}-{i}", schedule="every 5m", name=f"{tag}-{i}")
    print(json.dumps(len(list_jobs())))
    """
)


def _spawn_creator(tag, n, home, ready, go):
    env = {
        **os.environ,
        "MIMIR_AETHER_HOME": str(home),
        "PYTHONPATH": str(REPO_ROOT),
    }
    return subprocess.Popen(
        [sys.executable, "-c", _CHILD, tag, str(n), str(REPO_ROOT), ready, go],
        env=env,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_concurrent_two_process_create_no_lost_update(cron_home, tmp_path):
    """两进程各自 create_job ×15 并发：30 个全部在盘、id 全唯一（丢更新必红）。"""
    import cron.jobs as cj

    ready, go = tmp_path / "ready", tmp_path / "go"
    p1 = _spawn_creator("p1", 15, cron_home, str(ready) + ".1", str(go))
    p2 = _spawn_creator("p2", 15, cron_home, str(ready) + ".2", str(go))
    deadline = time.monotonic() + 30.0
    for marker in (ready.with_name("ready.1"), ready.with_name("ready.2")):
        while not marker.exists():
            assert time.monotonic() < deadline, "child never became ready"
            time.sleep(0.05)
    go.write_text("go")
    for p in (p1, p2):
        out, err = p.communicate(timeout=90)
        assert p.returncode == 0, f"child failed: {err}"

    raw = json.loads(cj.JOBS_FILE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict) and "jobs" in raw  # 字典形未破坏
    ids = [j["id"] for j in raw["jobs"]]
    assert len(ids) == 30, f"lost updates! got {len(ids)}: {ids}"
    assert len(set(ids)) == 30, "duplicate ids ⇒ lost-update overwrite"


def test_concurrent_cross_impl_writer_no_clobber(cron_home, tmp_path):
    """跨实现并发：cron/jobs.py（父进程）与 scheduler/jobs.py（子进程）
    同写一份 jobs.json —— 双方写入都存活、双方字段都不被回写毁掉。"""
    import cron.jobs as cj
    import scheduler.jobs as sj

    j0 = cj.create_job(prompt="keep-me", schedule="every 5m", name="base-0")
    j1 = cj.create_job(prompt="also-keep", schedule="every 5m", name="base-1")
    cj.update_job(j1["id"], {"enabled": False})

    child_script = textwrap.dedent(
        """
        import sys, time
        sys.path.insert(0, sys.argv[2])
        from scheduler.jobs import mark_job_run
        while not __import__("os").path.exists(sys.argv[3]):
            time.sleep(0.01)
        for _ in range(8):
            mark_job_run(sys.argv[1])
        """
    )
    go = tmp_path / "go2"
    env = {**os.environ, "MIMIR_AETHER_HOME": str(cron_home), "PYTHONPATH": str(REPO_ROOT)}
    child = subprocess.Popen(
        [sys.executable, "-c", child_script, j0["id"], str(REPO_ROOT), str(go)],
        env=env, cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    # 父进程同时持续用 cron/jobs.py 写（RMW 全量回写面）
    for i in range(8):
        cj.create_job(prompt=f"p-{i}", schedule="every 5m", name=f"parent-{i}")
    go.write_text("go")
    out, err = child.communicate(timeout=90)
    assert child.returncode == 0, f"child failed: {err}"

    jobs = {j["id"]: j for j in cj.load_jobs()}
    assert len(jobs) == 10, f"lost jobs cross-impl: {[j['name'] for j in jobs.values()]}"
    # scheduler 写的字段存活（float epoch 语义）
    assert isinstance(jobs[j0["id"]].get("last_run"), float)
    assert jobs[j0["id"]]["next_run"] > 0
    # cron 写的字段不被 scheduler 全量回写毁掉
    assert jobs[j0["id"]]["prompt"] == "keep-me"
    assert jobs[j1["id"]]["enabled"] is False
    assert jobs[j1["id"]]["prompt"] == "also-keep"


# ===========================================================================
# 形状与可重入
# ===========================================================================

def test_reentrant_window_no_deadlock(cron_home):
    import cron.jobs as cj

    with cj.write_window():
        with cj.write_window():
            cj.save_jobs([{"id": "a"}])
        cj.save_jobs([{"id": "a"}, {"id": "b"}])
    assert [j["id"] for j in cj.load_jobs()] == ["a", "b"]


def test_scheduler_mark_preserves_cron_dict_shape(cron_home):
    """scheduler 全量回写后仍是 ``{"jobs": [...]}`` 字典形（读容忍·写破坏回归）。"""
    import cron.jobs as cj
    import scheduler.jobs as sj

    j = cj.create_job(prompt="p", schedule="every 5m", name="shape")
    sj.mark_job_run(j["id"])
    raw = json.loads(cj.JOBS_FILE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict) and set(raw) == {"jobs"}
    job = cj.get_job(j["id"])
    assert job["prompt"] == "p" and job["schedule"]["type"] == "interval"
    assert isinstance(job["last_run"], float)
